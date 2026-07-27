import { ReviewerWelcome } from "@/components/review/reviewer-welcome";

export default async function ReviewerWelcomePage({
  searchParams,
}: {
  searchParams: Promise<{ lang?: string }>;
}) {
  const { lang } = await searchParams;
  return <ReviewerWelcome spanish={lang === "es"} />;
}
