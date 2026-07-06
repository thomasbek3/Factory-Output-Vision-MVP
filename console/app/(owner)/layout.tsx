import { OwnerChrome } from "@/components/chrome/owner-chrome";

export default function OwnerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <OwnerChrome>{children}</OwnerChrome>;
}
