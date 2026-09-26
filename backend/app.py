import sys
import os
import math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import timedelta
from functools import wraps

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from cryptography.fernet import Fernet, InvalidToken
from flask_jwt_extended import JWTManager, create_access_token, get_jwt, get_jwt_identity, jwt_required
import os
import json
import pyotp
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text as sql_text

from database import db
from integrations import analyze_claim_image, hf_request, index_policy_chunks, neo4j_claim_graph, neo4j_upsert_claim, retrieve_policy_chunks
from models import (
    Application,
    AuditLog,
    BillingTransaction,
    Claim,
    CustomerProfile,
    Policy,
    Provider,
    User,
)

app = Flask(__name__)
_frontend_origin = os.getenv("FRONTEND_ORIGIN", "").strip()
_allowed_origins = ["https://risk-sure-od3i.vercel.app"]
if _frontend_origin and _frontend_origin not in _allowed_origins:
    _allowed_origins.append(_frontend_origin)
CORS(
    app,
    resources={r"/*": {"origins": _allowed_origins}},
    supports_credentials=False,
)

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL") or "sqlite:///risksure.db"

# Vercel's Python runtime uses a PostgreSQL adapter explicitly configured here.
# Force SQLAlchemy onto psycopg 3 instead of implicitly resolving psycopg2.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql+psycopg2://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "").strip()
if os.getenv("FLASK_ENV", "").lower() == "production" and not JWT_SECRET:
    raise RuntimeError("JWT_SECRET_KEY must be configured in production")
if not JWT_SECRET:
    JWT_SECRET = "local-development-only-change-me"
app.config["JWT_SECRET_KEY"] = JWT_SECRET
jwt = JWTManager(app)
db.init_app(app)
limiter = Limiter(key_func=get_remote_address, app=app, default_limits=["300 per minute"])

with app.app_context():
    if os.getenv("AUTO_CREATE_TABLES", "false").lower() == "true":
        db.create_all()


VALID_ROLES = {"customer", "underwriter", "claims_officer", "provider", "admin"}
STAFF_ROLES = {"underwriter", "claims_officer", "provider", "admin"}
TOTP_REQUIRED_ROLES = VALID_ROLES

def _fernet():
    key = os.getenv("TOTP_ENCRYPTION_KEY", "").strip()
    if not key:
        return None
    return Fernet(key.encode())

def _encrypt_secret(secret):
    f = _fernet()
    if f is None:
        if os.getenv("FLASK_ENV") == "production":
            raise RuntimeError("TOTP_ENCRYPTION_KEY must be configured in production")
        return secret
    return f.encrypt(secret.encode()).decode()

def _decrypt_secret(secret):
    if not secret:
        return None
    f = _fernet()
    if f is None:
        return secret
    try:
        return f.decrypt(secret.encode()).decode()
    except InvalidToken:
        return secret



def generate_recovery_codes():
    return [os.urandom(6).hex().upper() for _ in range(8)]


def recovery_hashes(user):
    return json.loads(user.recovery_codes_hash) if user.recovery_codes_hash else []


def auth_token(user):
    return create_access_token(identity=str(user.id), additional_claims={"role": user.role})


def current_user_record():
    identity = get_jwt_identity()
    try:
        user_id = int(identity)
    except (TypeError, ValueError):
        return None
    return db.session.get(User, user_id)


def roles_required(*allowed_roles):
    allowed = set(allowed_roles)

    def decorator(view):
        @wraps(view)
        @jwt_required()
        def wrapped(*args, **kwargs):
            user = current_user_record()
            if user is None:
                return jsonify({"error": "User not found"}), 404
            if user.role not in allowed:
                return jsonify({"error": "Insufficient permissions"}), 403
            return view(*args, **kwargs)

        return wrapped

    return decorator


def customer_for_user(user):
    return CustomerProfile.query.filter_by(user_id=user.id).first()


def audit(user_id, action, entity_type=None, entity_id=None, details=None):
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=json.dumps(details) if isinstance(details, (dict, list)) else details,
    )
    db.session.add(entry)


def claim_to_dict(claim):
    return {
        "id": claim.id,
        "claim_number": claim.claim_number,
        "customer_id": claim.customer_id,
        "policy_id": claim.policy_id,
        "provider_id": claim.provider_id,
        "status": claim.status,
        "claimed_amount": claim.claimed_amount,
        "approved_amount": claim.approved_amount,
        "assigned_officer_id": claim.assigned_officer_id,
        "incident_date": claim.incident_date.isoformat() if claim.incident_date else None,
        "description": claim.description,
        "created_at": claim.created_at.isoformat() if claim.created_at else None,
        "updated_at": claim.updated_at.isoformat() if claim.updated_at else None,
    }


def provider_for_user(user):
    return Provider.query.filter_by(user_id=user.id).first()



MODEL_DIR = os.path.join(os.path.dirname(__file__), "model")
model_loaded = False
model = None
explainer = None
feature_names = ["age", "sex", "bmi", "children", "smoker", "region"]
min_charge = 1000.0
max_charge = 50000.0

print("ML model packages are kept outside the Vercel runtime to keep the function within size limits.")
model_loaded = False
model = None
explainer = None


@app.route("/")
def home():
    status = "LOADED" if model_loaded else "FAILED"
    return f"Backend is running.<br><br>ML Model Status: {status}"


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "RiskSure backend",
        "model_loaded": model_loaded,
    })


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    if "status" in data:
        status = str(data["status"]).strip().lower()
        if status not in {"submitted", "under_review", "approved", "rejected", "settled"}:
            return jsonify({"error": "Invalid claim status"}), 400
        claim.status = status
    if "approved_amount" in data:
        try:
            approved_amount = float(data["approved_amount"])
        except (TypeError, ValueError):
            return jsonify({"error": "Approved amount must be numeric"}), 400
        if not math.isfinite(approved_amount) or approved_amount < 0:
            return jsonify({"error": "Approved amount must be a finite non-negative number"}), 400
        if approved_amount > claim.claimed_amount:
            return jsonify({"error": "Approved amount cannot exceed the claimed amount"}), 400
        claim.approved_amount = approved_amount
    if "assigned_officer_id" in data:
        try:
            officer_id = int(data["assigned_officer_id"])
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid claims officer"}), 400
        officer = db.session.get(User, officer_id)
        if officer is None or officer.role != "claims_officer":
            return jsonify({"error": "Invalid claims officer"}), 400
        claim.assigned_officer_id = officer.id

    audit(user.id, "claim_updated", "claim", claim.id, data)
    db.session.commit()
    return jsonify({"message": "Claim updated", "claim": claim_to_dict(claim)})


@app.route("/providers/me", methods=["GET"])
@roles_required("provider", "admin")
def provider_me():
    provider = provider_for_user(current_user_record())
    if provider is None:
        return jsonify({"error": "Provider profile not found"}), 404
    return jsonify({
        "id": provider.id,
        "name": provider.name,
        "provider_type": provider.provider_type,
        "license_number": provider.license_number,
        "status": provider.status,
        "phone": provider.phone,
        "address": provider.address,
        "city": provider.city,
        "state": provider.state,
    })


@app.route("/providers/me/claims", methods=["GET"])
@roles_required("provider", "admin")
def provider_claims():
    provider = provider_for_user(current_user_record())
    if provider is None:
        return jsonify([])
    claims = Claim.query.filter_by(provider_id=provider.id).order_by(Claim.created_at.desc()).all()
    return jsonify([claim_to_dict(c) for c in claims])


@app.route("/admin/users", methods=["GET"])
@roles_required("admin")
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify([user.to_dict() for user in users])


@app.route("/admin/users/<int:user_id>/role", methods=["PUT"])
@roles_required("admin")
def admin_update_role(user_id):
    admin = current_user_record()
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(silent=True) or {}
    role = str(data.get("role", "")).strip().lower()
    if role not in VALID_ROLES:
        return jsonify({"error": "Invalid role"}), 400
    if user.id == admin.id and role != "admin":
        return jsonify({"error": "An admin cannot remove their own admin role"}), 400

    user.role = role
    audit(admin.id, "user_role_changed", "user", user.id, {"role": role})
    db.session.commit()
    return jsonify({"message": "Role updated", "user": user.to_dict()})


@app.route("/admin/audit-logs", methods=["GET"])
@roles_required("admin")
def admin_audit_logs():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return jsonify([{
        "id": log.id,
        "user_id": log.user_id,
        "action": log.action,
        "entity_type": log.entity_type,
        "entity_id": log.entity_id,
        "details": log.details,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    } for log in logs])


@app.route("/admin/overview", methods=["GET"])
@roles_required("admin")
def admin_overview():
    return jsonify({
        "users": User.query.count(),
        "customers": CustomerProfile.query.count(),
        "providers": Provider.query.count(),
        "policies": Policy.query.count(),
        "applications": Application.query.count(),
        "claims": Claim.query.count(),
        "billing_transactions": BillingTransaction.query.count(),
    })



def policy_to_dict(policy):
    return {"id":policy.id,"policy_number":policy.policy_number,"customer_id":policy.customer_id,"provider_id":policy.provider_id,"policy_type":policy.policy_type,"status":policy.status,"coverage_limit":policy.coverage_limit,"premium_amount":policy.premium_amount,"start_date":policy.start_date.isoformat() if policy.start_date else None,"end_date":policy.end_date.isoformat() if policy.end_date else None,"terms_document":policy.terms_document}

@app.route("/policies",methods=["GET"])
@roles_required("customer","admin","underwriter","claims_officer","provider")
def list_policies():
    u=current_user_record(); q=Policy.query
    if u.role=="customer":
        p=customer_for_user(u); q=q.filter_by(customer_id=p.id) if p else q.filter_by(id=-1)
    if u.role=="provider":
        p=provider_for_user(u); q=q.filter_by(provider_id=p.id) if p else q.filter_by(id=-1)
    return jsonify([policy_to_dict(p) for p in q.order_by(Policy.created_at.desc()).all()])

@app.route("/policies/<int:policy_id>/document",methods=["PUT"])
@roles_required("admin","underwriter","claims_officer")
def policy_document(policy_id):
    p=db.session.get(Policy,policy_id)
    if not p:return jsonify({"error":"Policy not found"}),404
    text=str((request.get_json(silent=True) or {}).get("document_text","")).strip()
    if not text:return jsonify({"error":"document_text is required"}),400
    p.terms_document=text;audit(current_user_record().id,"policy_document_indexed","policy",p.id,{"characters":len(text)});db.session.commit()
    return jsonify({"message":"Policy document indexed","policy":policy_to_dict(p)})

@app.route("/policies/<int:policy_id>/intelligence",methods=["POST"])
@roles_required("customer","admin","underwriter","claims_officer","provider")
def policy_intelligence(policy_id):
    p=db.session.get(Policy,policy_id)
    if not p:return jsonify({"error":"Policy not found"}),404
    u=current_user_record()
    if u.role=="customer":
        profile=customer_for_user(u)
        if profile is None or p.customer_id != profile.id:
            return jsonify({"error":"Insufficient permissions"}),403
    elif u.role=="provider":
        provider=provider_for_user(u)
        if provider is None or p.provider_id != provider.id:
            return jsonify({"error":"Insufficient permissions"}),403
    d=request.get_json(silent=True) or {};text=str(d.get("document_text") or p.terms_document or "").strip();q=str(d.get("question") or "").strip()
    if not text:return jsonify({"error":"No policy document text available"}),400
    parts=[v.strip() for v in text.replace("\r","").split("\n") if v.strip()];words={w.lower() for w in q.split() if len(w)>2};hits=sorted(parts,key=lambda v:sum(w in v.lower() for w in words),reverse=True)[:3]
    try:
        indexed = index_policy_chunks(p.id, parts)
        retrieved = retrieve_policy_chunks(p.id, q) if q else []
    except Exception:
        indexed = 0
        retrieved = []
    context = retrieved or [{"text":v,"section":i+1} for i,v in enumerate(hits)]
    try:
        generated = hf_request("Answer the insurance policy question using only this policy text. If the answer is not specified, say so. Question: " + q + "\\nPolicy text:\\n" + "\\n".join(x["text"] for x in context)) if q else None
    except Exception:
        generated = None
    audit(current_user_record().id,"policy_intelligence_query","policy",p.id,{"question":q});db.session.commit()
    return jsonify({"policy":policy_to_dict(p),"question":q,"answer":generated or " ".join(x["text"] for x in context)[:4000],"sources":context,"retrieval":"Chroma + Hugging Face" if retrieved else "RiskSure policy retrieval","indexed_chunks":indexed})

@app.route("/fraud/investigation/<int:claim_id>",methods=["GET"])
@roles_required("claims_officer","underwriter","admin")
def fraud_investigation(claim_id):
    c=db.session.get(Claim,claim_id)
    if not c:return jsonify({"error":"Claim not found"}),404
    related=Claim.query.filter((Claim.customer_id==c.customer_id)|(Claim.provider_id==c.provider_id)).all();signals=[]
    if len([x for x in related if x.customer_id==c.customer_id])>=3:signals.append({"type":"repeat_customer","severity":"medium"})
    if c.provider_id and len([x for x in related if x.provider_id==c.provider_id])>=3:signals.append({"type":"repeat_provider","severity":"medium"})
    if (c.claimed_amount or 0)>100000:signals.append({"type":"high_amount","severity":"high"})
    score=min(1.0,.2*len(signals)+.05*max(0,len(related)-1))
    audit(current_user_record().id,"fraud_investigation_viewed","claim",c.id,{"anomaly_score":score});db.session.commit()
    try:
        neo4j_upsert_claim({"customer_id":c.customer_id,"claim_id":c.id,"claim_number":c.claim_number,"amount":c.claimed_amount,"status":c.status,"provider_id":c.provider_id})
        graph_from_neo4j=neo4j_claim_graph(c.id)
    except Exception:
        graph_from_neo4j={"nodes":[],"edges":[]}
    nodes=graph_from_neo4j["nodes"] or [{"id":"customer-"+str(c.customer_id),"type":"customer"},{"id":"claim-"+str(c.id),"type":"claim"}]
    edges=graph_from_neo4j["edges"] or [{"source":"customer-"+str(c.customer_id),"target":"claim-"+str(c.id),"relationship":"submitted"}]
    if c.provider_id:nodes.append({"id":"provider-"+str(c.provider_id),"type":"provider"});edges.append({"source":"provider-"+str(c.provider_id),"target":"claim-"+str(c.id),"relationship":"submitted_to"})
    return jsonify({"claim":claim_to_dict(c),"graph":{"nodes":nodes,"edges":edges},"anomaly_score":round(score,3),"signals":signals,"recommendation":"Human investigation recommended." if signals else "No configured anomaly signal detected."})

@app.route("/billing",methods=["GET"])
@roles_required("customer","admin")
def billing_list():
    u=current_user_record();q=BillingTransaction.query
    if u.role=="customer":
        p=customer_for_user(u);q=q.filter_by(customer_id=p.id) if p else q.filter_by(id=-1)
    return jsonify([{"id":x.id,"policy_id":x.policy_id,"claim_id":x.claim_id,"transaction_type":x.transaction_type,"amount":x.amount,"status":x.status,"reference":x.reference,"description":x.description,"created_at":x.created_at.isoformat() if x.created_at else None} for x in q.order_by(BillingTransaction.created_at.desc()).all()])

@app.route("/billing",methods=["POST"])
@roles_required("customer","admin")
def billing_create():
    u=current_user_record();d=request.get_json(silent=True) or {}
    try:
        amount = float(d["amount"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error":"Valid amount is required"}),400
    if not math.isfinite(amount) or amount <= 0:
        return jsonify({"error":"Amount must be a finite number greater than zero"}),400

    transaction_type = str(d.get("transaction_type","premium")).strip().lower()
    if transaction_type not in {"premium", "claim_payment", "refund", "adjustment"}:
        return jsonify({"error":"Invalid transaction type"}),400
    status = str(d.get("status","pending")).strip().lower()
    if status not in {"pending", "paid", "failed", "refunded"}:
        return jsonify({"error":"Invalid transaction status"}),400

    try:
        policy_id = int(d["policy_id"]) if d.get("policy_id") is not None else None
        claim_id = int(d["claim_id"]) if d.get("claim_id") is not None else None
    except (TypeError, ValueError):
        return jsonify({"error":"Invalid policy or claim identifier"}),400

    if u.role=="customer":
        p=customer_for_user(u)
    else:
        try:
            customer_id = int(d.get("customer_id",0))
        except (TypeError, ValueError):
            return jsonify({"error":"Invalid customer identifier"}),400
        p=db.session.get(CustomerProfile, customer_id)

    if not p:return jsonify({"error":"Customer profile not found"}),404

    policy = db.session.get(Policy, policy_id) if policy_id is not None else None
    if policy_id is not None and policy is None:
        return jsonify({"error":"Policy not found"}),404
    if policy is not None and policy.customer_id != p.id:
        return jsonify({"error":"Policy does not belong to this customer"}),403

    claim = db.session.get(Claim, claim_id) if claim_id is not None else None
    if claim_id is not None and claim is None:
        return jsonify({"error":"Claim not found"}),404
    if claim is not None:
        if claim.customer_id != p.id:
            return jsonify({"error":"Claim does not belong to this customer"}),403
        if policy is not None and claim.policy_id != policy.id:
            return jsonify({"error":"Claim does not belong to the selected policy"}),400

    t=BillingTransaction(customer_id=p.id,policy_id=policy_id,claim_id=claim_id,transaction_type=transaction_type,amount=amount,status=status,reference="RS-BILL-"+os.urandom(5).hex().upper(),description=str(d.get("description","")))

    db.session.add(t);db.session.flush();audit(u.id,"billing_transaction_created","billing_transaction",t.id);db.session.commit();return jsonify({"message":"Billing transaction created","id":t.id,"reference":t.reference}),201

@app.route("/customer/portal",methods=["GET"])
@roles_required("customer")
def customer_portal():
    u=current_user_record();p=customer_for_user(u)
    if not p:return jsonify({"error":"Customer profile not found"}),404
    return jsonify({"profile":{"id":p.id,"full_name":p.full_name,"phone":p.phone,"city":p.city,"state":p.state},"policies":[policy_to_dict(x) for x in Policy.query.filter_by(customer_id=p.id).all()],"claims":[claim_to_dict(x) for x in Claim.query.filter_by(customer_id=p.id).all()],"applications":[x.to_dict() for x in Application.query.filter_by(customer_id=p.id).all()]})

@app.route("/cases/<int:application_id>/intelligence",methods=["GET"])
@roles_required("underwriter","claims_officer","admin")
def unified_case_intelligence(application_id):
    a=db.session.get(Application,application_id)
    if not a:return jsonify({"error":"Application not found"}),404
    claims=Claim.query.filter_by(customer_id=a.customer_id).all() if a.customer_id else [];p=Policy.query.filter_by(customer_id=a.customer_id).first() if a.customer_id else None
    signals=[{"claim_id":c.id,"provider_id":c.provider_id} for c in claims if c.provider_id]
    consistency=["High-value claim requires human review."] if any((c.claimed_amount or 0)>100000 for c in claims) else []
    return jsonify({"application":a.to_dict(),"risk":{"model_score":a.risk_score,"final_risk":a.final_risk,"decision":a.decision},"policy":policy_to_dict(p) if p else None,"claims":[claim_to_dict(c) for c in claims],"relationship_signals":signals,"document_consistency":consistency,"human_review_required":bool(consistency or a.review_status in {"manual_review","in_review"})})

@app.route("/graph/claim/<int:claim_id>",methods=["GET"])
@roles_required("claims_officer","underwriter","admin")
def claim_graph(claim_id):
    c=db.session.get(Claim,claim_id)
    if not c:return jsonify({"error":"Claim not found"}),404
    related=Claim.query.filter((Claim.customer_id==c.customer_id)|(Claim.provider_id==c.provider_id)).all()
    nodes=[];edges=[]
    def add(n,t): 
        if not any(x["id"]==n for x in nodes):nodes.append({"id":n,"type":t})
    add("customer-"+str(c.customer_id),"customer")
    for x in related:
        add("claim-"+str(x.id),"claim");edges.append({"source":"customer-"+str(c.customer_id),"target":"claim-"+str(x.id),"relationship":"submitted"})
        if x.provider_id:
            add("provider-"+str(x.provider_id),"provider");edges.append({"source":"provider-"+str(x.provider_id),"target":"claim-"+str(x.id),"relationship":"submitted_to"})
    return jsonify({"nodes":nodes,"edges":edges})

@app.route("/claims/<int:claim_id>/intelligence",methods=["POST"])
@roles_required("claims_officer","underwriter","admin")
def claim_intelligence(claim_id):
    c=db.session.get(Claim,claim_id)
    if not c:return jsonify({"error":"Claim not found"}),404
    d=request.get_json(silent=True) or {};text=str(d.get("document_text","")).strip()
    extracted={"claim_number":c.claim_number,"claimed_amount":c.claimed_amount,"document_present":bool(text)}
    signals=[]
    if text and c.claimed_amount and str(c.claimed_amount) not in text:signals.append("Claimed amount was not found verbatim in supplied document.")
    if c.claimed_amount and c.claimed_amount>100000:signals.append("High-value claim requires human review.")
    return jsonify({"claim":claim_to_dict(c),"extracted":extracted,"signals":signals,"human_review_required":bool(signals)})

@app.route("/claims/<int:claim_id>/image-intelligence",methods=["POST"])
@roles_required("claims_officer","underwriter","admin")
def claim_image_intelligence(claim_id):
    c=db.session.get(Claim,claim_id)
    if not c:return jsonify({"error":"Claim not found"}),404
    d=request.get_json(silent=True) or {}
    path=str(d.get("image_path","")).strip()
    if not path:return jsonify({"error":"image_path is required"}),400
    return jsonify({"claim":claim_to_dict(c),"image_analysis":analyze_claim_image(path)})

@app.route("/cases/<int:application_id>/review",methods=["GET"])
@roles_required("underwriter","claims_officer","admin")
def case_review(application_id):
    a=db.session.get(Application,application_id)
    if not a:return jsonify({"error":"Application not found"}),404
    intelligence=unified_case_intelligence(application_id)
    return intelligence

@app.route("/health/detailed",methods=["GET"])
def detailed_health():
    return jsonify({"status":"ok","database":db.session.execute(sql_text("SELECT 1")).scalar()==1,"model_loaded":model is not None,"environment":os.getenv("FLASK_ENV","development")})

@app.route("/integrations/status",methods=["GET"])
@roles_required("admin")
def integrations_status():
    return jsonify({
        "postgres": bool(os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL")),
        "neo4j": bool(os.getenv("NEO4J_URI") and os.getenv("NEO4J_USERNAME") and os.getenv("NEO4J_PASSWORD")),
        "huggingface": bool(os.getenv("HUGGINGFACE_API_TOKEN")),
        "chroma": bool(os.getenv("CHROMA_HOST")),
        "frontend_origin": bool(os.getenv("FRONTEND_ORIGIN"))
    })

if __name__ == "__main__":
    print("Starting Flask server...")
    print(f"Model loaded: {model_loaded}")
    app.run(host="0.0.0.0", port=5000, debug=True)
