import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Ecossistema PDHC III",
  description: "Plataforma de Desenvolvimento das Cadeias Produtivas da Agricultura Familiar",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script
          // Aplica a preferência de tema salva ANTES do paint, evitando flash
          // entre claro/escuro durante a hidratação. Quando não houver
          // preferência, o navegador segue prefers-color-scheme do sistema.
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem('theme');if(t==='light'||t==='dark'){document.documentElement.setAttribute('data-theme',t);}}catch(_){}`,
          }}
        />
      </head>
      <body className="min-h-full flex flex-col">
        {/* A sessão é da área logada: o SessionProvider fica no layout dela,
            com a sessão já lida no servidor (#448). O login só usa signIn(). */}
        {children}
      </body>
    </html>
  );
}
