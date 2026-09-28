import type { Metadata } from 'next';
import './globals.css';
export const metadata:Metadata={title:'FYD • For You Dillu',description:'Your personal B.Pharmacy study companion.'};
export default function Layout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}
