import { Account } from "@/features/Account";
export const metadata = { title: "Phone sign-in" };
export default async function Login({
  searchParams,
}: {
  searchParams: Promise<{ role?: string }>;
}) {
  return (
    <Account
      intent={(await searchParams).role === "employer" ? "employer" : "worker"}
    />
  );
}
