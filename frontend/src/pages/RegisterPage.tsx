import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!username.trim() || !email.trim() || !password) return;
    setLoading(true);
    setError(null);
    try {
      await register(username.trim(), email.trim(), password);
      navigate("/", { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f4f4f7] px-4">
      <div className="w-full max-w-sm rounded-2xl border border-zinc-200 bg-white p-8 shadow-lg">
        <div className="mb-6 flex flex-col items-center">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent text-lg font-bold text-white">
            S
          </span>
          <h1 className="mt-3 text-xl font-bold text-zinc-900">Create an account</h1>
          <p className="mt-1 text-sm text-zinc-500">Get started with Stylist AI</p>
        </div>

        <label className="mb-1 block text-xs font-semibold text-zinc-600">Username</label>
        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !loading) void submit(); }}
          disabled={loading}
          placeholder="Your name"
          className="mb-4 w-full rounded-xl border border-zinc-200 px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-accent/30 disabled:opacity-50"
        />

        <label className="mb-1 block text-xs font-semibold text-zinc-600">Email</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !loading) void submit(); }}
          disabled={loading}
          placeholder="you@example.com"
          className="mb-4 w-full rounded-xl border border-zinc-200 px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-accent/30 disabled:opacity-50"
        />

        <label className="mb-1 block text-xs font-semibold text-zinc-600">Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !loading) void submit(); }}
          disabled={loading}
          placeholder="Min. 6 characters"
          className="mb-4 w-full rounded-xl border border-zinc-200 px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-accent/30 disabled:opacity-50"
        />

        {error && <p className="mb-4 text-xs text-red-600">{error}</p>}

        <button
          type="button"
          onClick={() => void submit()}
          disabled={loading || !username.trim() || !email.trim() || !password}
          className="w-full rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-[#4f4ddb] disabled:opacity-40"
        >
          {loading ? "Creating account..." : "Create account"}
        </button>

        <p className="mt-5 text-center text-sm text-zinc-500">
          Already have an account?{" "}
          <Link to="/login" className="font-semibold text-accent hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
