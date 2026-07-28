import { ReviewerWelcome } from "@/components/review/reviewer-welcome";

export default async function ReviewerWelcomePage({
  searchParams,
}: {
  searchParams: Promise<{ lang?: string; mode?: string }>;
}) {
  const { lang, mode } = await searchParams;
  return (
    <ReviewerWelcome
      spanish={lang === "es"}
      passwordless={mode === "login"}
    />
  );
}
