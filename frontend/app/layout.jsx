import "./globals.css";

export const metadata = {
  title: "Barangay Equipment Borrowing System",
  description: "Equipment inventory and borrowing management"
};

export default function RootLayout({ children }) {
  return <html lang="en"><body>{children}</body></html>;
}
