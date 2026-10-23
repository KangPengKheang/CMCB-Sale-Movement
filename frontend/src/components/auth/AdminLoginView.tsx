import React, { useState } from "react";
import { Lock, Eye, EyeOff, Loader2, ShieldCheck, ArrowRight } from "lucide-react";
import { loginAdmin, type SessionUser } from "../../services/api";

interface AdminLoginViewProps {
  onLoginSuccess: (user: SessionUser) => void;
  onGoToSales: () => void;
}

export const AdminLoginView: React.FC<AdminLoginViewProps> = ({
  onLoginSuccess,
  onGoToSales,
}) => {
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password) {
      setErrorMessage("Please enter your password.");
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    const res = await loginAdmin(password);
    setIsLoading(false);

    if (res.success && res.user) {
      onLoginSuccess(res.user);
    } else {
      setErrorMessage(res.error || "Password not accepted.");
    }
  };

  return (
    <div className="min-h-screen w-full bg-slate-900 flex flex-col justify-center items-center p-4 select-none relative overflow-hidden">
      {/* Background Decorative Ambient Glows */}
      <div className="absolute -top-40 -left-40 w-96 h-96 bg-cmcb-700/20 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-emerald-600/20 rounded-full blur-3xl pointer-events-none" />

      {/* Login Card */}
      <div className="w-full max-w-md bg-white rounded-3xl shadow-2xl border border-slate-200/80 p-8 sm:p-10 relative z-10 space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center h-16 w-16 rounded-2xl bg-cmcb-50 border border-cmcb-100 shadow-xs mb-1">
            <img
              src="/CMCB_small_icon.png"
              alt="CMCB"
              className="h-10 w-10 object-contain"
              onError={(e) => {
                // Fallback to shield icon if image path is altered
                (e.target as HTMLElement).style.display = "none";
              }}
            />
            <ShieldCheck className="h-8 w-8 text-cmcb-700 hidden only:block" />
          </div>

          <h1 className="text-2xl font-black tracking-tight text-slate-900">
            CMCB Sales Monitor
          </h1>
          <p className="text-xs text-slate-500 font-medium">
            Retail Intelligence & Market Analytics Platform
          </p>
        </div>

        {/* Error Alert Banner */}
        {errorMessage && (
          <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-semibold flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-rose-500 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Password Field */}
          <div className="space-y-1.5">
            <label htmlFor="login-password" className="text-xs font-bold text-slate-700 block">
              Password
            </label>
            <div className="relative flex items-center">
              <Lock className="absolute left-3.5 h-4 w-4 text-slate-400" />
              <input
                id="login-password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••••••••••"
                disabled={isLoading}
                autoComplete="current-password"
                autoFocus
                required
                maxLength={1024}
                className="w-full rounded-xl border border-slate-200 bg-slate-50/50 py-2.5 pl-10 pr-11 text-sm font-semibold text-slate-900 placeholder-slate-400 focus:bg-white focus:border-cmcb-600 focus:outline-none focus:ring-1 focus:ring-cmcb-600 transition-all"
              />
              <button
                type="button"
                aria-label={showPassword ? "Hide password" : "Show password"}
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3.5 text-slate-400 hover:text-slate-600 focus:outline-none"
              >
                {showPassword ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isLoading}
            className="w-full mt-2 rounded-xl bg-cmcb-700 hover:bg-cmcb-800 active:bg-cmcb-900 text-white font-extrabold text-sm py-3 px-4 shadow-md transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-70"
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Verifying credentials...</span>
              </>
            ) : (
              <span>Sign in</span>
            )}
          </button>
        </form>

        {/* Divider & Switch to Sales Portal */}
        <div className="pt-4 border-t border-slate-100 text-center">
          <p className="text-xs text-slate-500 font-medium mb-2">
            Enter your Users sheet password to access your permitted channels.
          </p>
          <button
            onClick={onGoToSales}
            className="inline-flex items-center gap-1.5 text-xs font-bold text-cmcb-700 hover:text-cmcb-800 transition-colors cursor-pointer"
          >
            <span>Open Field Sales Portal</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Footer Info */}
      <p className="text-slate-500 text-[11px] font-semibold mt-6 relative z-10 text-center">
        Chip Mong Commercial Bank PLC · Internal Market Analytics
      </p>
    </div>
  );
};
