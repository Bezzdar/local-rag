import './globals.css';
import { ReactNode } from 'react';
import Providers from '@/components/providers';
import StoreInitializer from '@/components/StoreInitializer';

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body>
        <Providers>
          <StoreInitializer />
          {children}
        </Providers>
      </body>
    </html>
  );
}
