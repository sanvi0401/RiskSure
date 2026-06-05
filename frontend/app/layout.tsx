import type { Metadata } from 'next'
import { IBM_Plex_Mono, Sora } from 'next/font/google'
import { Analytics } from '@vercel/analytics/next'
import { ApplicationProvider } from '@/context/application-context'
import './globals.css'

const sora = Sora({
  subsets: ['latin'],
  variable: '--font-sora',
})

const plexMono = IBM_Plex_Mono({
  subsets: ['latin'],
  variable: '--font-plex-mono',
  weight: ['400', '500', '600'],
})

export const metadata: Metadata = {
  title: 'RiskSure - Healthcare Insurance Admin',
  description: 'Admin dashboard for healthcare insurance applications',
  generator: 'v0.app',
  icons: {
    icon: [
      {
        url: '/icon-light-32x32.png',
        media: '(prefers-color-scheme: light)',
      },
      {
        url: '/icon-dark-32x32.png',
        media: '(prefers-color-scheme: dark)',
      },
      {
        url: '/icon.svg',
        type: 'image/svg+xml',
      },
    ],
    apple: '/apple-icon.png',
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${sora.variable} ${plexMono.variable} font-sans antialiased`}>
        <ApplicationProvider>
          {children}
        </ApplicationProvider>
        <Analytics />
      </body>
    </html>
  )
}
