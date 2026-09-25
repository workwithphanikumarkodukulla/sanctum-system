"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Lock, ArrowRight, ShieldCheck, KeyRound, X, Sparkles } from "lucide-react";
import { useTheme } from "@/lib/theme";

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLoginSuccess: () => void;
}

export const LoginModal: React.FC<LoginModalProps> = ({
  isOpen,
  onClose,
  onLoginSuccess,
}) => {
  const [passphrase, setPassphrase] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const { theme } = useTheme();
  const isLight = theme === "light";

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
      onLoginSuccess();
    }, 500);
  };

  const handleQuickEnter = () => {
    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
      onLoginSuccess();
    }, 400);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className={`fixed inset-0 backdrop-blur-md transition-colors ${
              isLight ? "bg-slate-900/40" : "bg-black/80"
            }`}
          />

          {/* Modal Content */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 15 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 15 }}
            transition={{ duration: 0.2 }}
            className={`relative w-full max-w-md rounded-2xl p-6 shadow-2xl z-10 space-y-5 border transition-colors ${
              isLight
                ? "bg-white border-[#e2e8f0] text-[#0f172a] shadow-slate-900/15"
                : "bg-[#121212]/95 border-[#2a2a2a] text-white shadow-black"
            }`}
          >
            {/* Close */}
            <button
              onClick={onClose}
              className={`absolute top-4 right-4 p-1.5 rounded-lg transition-colors cursor-pointer ${
                isLight
                  ? "text-slate-400 hover:text-slate-700 hover:bg-slate-100"
                  : "text-neutral-400 hover:text-white hover:bg-white/10"
              }`}
            >
              <X className="w-4 h-4" />
            </button>

            {/* Header */}
            <div className="space-y-1.5 text-center">
              <div
                className={`w-10 h-10 rounded-xl mx-auto flex items-center justify-center shadow-lg border ${
                  isLight
                    ? "bg-[#ecf7dc] border-[#22c55e]/40 text-[#15803d] shadow-emerald-700/10"
                    : "bg-[#1a2512] border-[#76B900]/40 text-[#76B900] shadow-[#76B900]/10"
                }`}
              >
                <Lock className="w-5 h-5" />
              </div>
              <h2
                className={`text-lg font-bold tracking-tight ${
                  isLight ? "text-[#0f172a]" : "text-white"
                }`}
              >
                Enter Sovereign Studio
              </h2>
              <p className={`text-xs ${isLight ? "text-[#64748b]" : "text-neutral-400"}`}>
                Local-first desktop agent environment with 100% loopback privacy.
              </p>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label
                  className={`block text-xs font-mono mb-1.5 flex items-center gap-1.5 ${
                    isLight ? "text-[#334155]" : "text-neutral-300"
                  }`}
                >
                  <KeyRound className="w-3.5 h-3.5 text-[#16a34a]" />
                  <span>Passphrase or Security Token</span>
                </label>
                <input
                  type="password"
                  value={passphrase}
                  onChange={(e) => setPassphrase(e.target.value)}
                  placeholder="Enter passphrase (or click Launch Studio)..."
                  className={`w-full rounded-xl px-3.5 py-2.5 text-xs focus:outline-none font-mono transition-colors border ${
                    isLight
                      ? "bg-[#f8fafc] border-[#cbd5e1] text-[#0f172a] placeholder-slate-400 focus:border-[#16a34a]"
                      : "bg-[#181818] border-[#2e2e2e] text-white placeholder-neutral-500 focus:border-[#76B900]"
                  }`}
                />
              </div>

              <div className="space-y-2">
                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full py-2.5 rounded-xl bg-gradient-to-r from-[#22c55e] to-[#16a34a] hover:from-[#16a34a] hover:to-[#15803d] text-white font-semibold text-xs flex items-center justify-center gap-2 transition-all cursor-pointer shadow-lg shadow-green-900/25"
                >
                  {isLoading ? (
                    <span className="flex items-center gap-2">
                      <span className="w-3 h-3 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                      Authenticating Local Node...
                    </span>
                  ) : (
                    <>
                      <span>Enter Studio</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </>
                  )}
                </button>

                <button
                  type="button"
                  onClick={handleQuickEnter}
                  className={`w-full py-2 rounded-xl border text-xs font-mono flex items-center justify-center gap-2 transition-colors cursor-pointer ${
                    isLight
                      ? "bg-[#f1f5f9] hover:bg-[#e2e8f0] border-[#cbd5e1] text-[#334155]"
                      : "bg-[#1a1a1a] hover:bg-[#222] border-[#333] text-neutral-300 hover:text-white"
                  }`}
                >
                  <Sparkles className="w-3.5 h-3.5 text-[#16a34a]" />
                  <span>Instant Studio Access (Demo Mode)</span>
                </button>
              </div>
            </form>

            <div
              className={`pt-2 border-t flex items-center justify-between text-[11px] font-mono ${
                isLight
                  ? "border-[#e2e8f0] text-[#64748b]"
                  : "border-[#222] text-neutral-500"
              }`}
            >
              <span className="flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5 text-[#16a34a]" />
                Zero Cloud Egress
              </span>
              <span>127.0.0.1:5050</span>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
