import type { Metadata } from 'next'
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

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" data-theme="burgundy">
      <head>
        <script src="https://mcp.figma.com/mcp/html-to-design/capture.js" async></script>
      </head>
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
