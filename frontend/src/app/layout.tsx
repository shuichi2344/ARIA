import type { Metadata } from 'next'
import { headers } from 'next/headers'
import { Inter, Space_Grotesk, Caveat } from 'next/font/google'
import './globals.css'
import { SessionProvider } from '@/context/SessionContext'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
})

const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  weight: ['700'],
  variable: '--font-display',
})

const caveat = Caveat({
  subsets: ['latin'],
  weight: ['600', '700'],
  variable: '--font-cursive',
})

export const metadata: Metadata = {
  title: 'ARIA – Agentic Retail Intelligence & Analytics',
  description:
    'Predict customer behaviour before it happens. AI-powered agent-based simulations for Malaysian SMEs.',
}

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  // Nonce-based CSP requires Next.js to render each document on the server.
  await headers()

  return (
    <html lang="en" data-theme="burgundy">
      <body
        className={`${inter.variable} ${spaceGrotesk.variable} ${caveat.variable} antialiased`}
      >
        <SessionProvider>
            {children}
          </SessionProvider>
      </body>
    </html>
  )
}
