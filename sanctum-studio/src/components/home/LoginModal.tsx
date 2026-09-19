"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Lock, ArrowRight, ShieldCheck, KeyRound, X, Sparkles } from "lucide-react";

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
            className="fixed inset-0 bg-black/80 backdrop-blur-md"
          />

          {/* Modal Content */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 15 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 15 }}
            transition={{ duration: 0.2 }}
            className="relative w-full max-w-md bg-[#121212]/95 border border-[#2a2a2a] rounded-2xl p-6 shadow-2xl shadow-black z-10 space-y-5"
          >
            {/* Close */}
            <button
              onClick={onClose}
              className="absolute top-4 right-4 p-1.5 text-neutral-400 hover:text-white rounded-lg hover:bg-white/10 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>

            {/* Header */}
            <div className="space-y-1.5 text-center">
              <div className="w-10 h-10 rounded-xl bg-[#1a2512] border border-[#76B900]/40 mx-auto flex items-center justify-center text-[#76B900] shadow-lg shadow-[#76B900]/10">
                <Lock className="w-5 h-5" />
              </div>
              <h2 className="text-lg font-bold text-white tracking-tight">
                Enter Sovereign Studio
              </h2>
              <p className="text-xs text-neutral-400">
                Local-first desktop agent environment with 100% loopback privacy.
              </p>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-mono text-neutral-300 mb-1.5 flex items-center gap-1.5">
                  <KeyRound className="w-3.5 h-3.5 text-[#76B900]" />
                  <span>Passphrase or Security Token</span>
                </label>
                <input
                  type="password"
                  value={passphrase}
                  onChange={(e) => setPassphrase(e.target.value)}
                  placeholder="Enter passphrase (or click Launch Studio)..."
                  className="w-full bg-[#181818] border border-[#2e2e2e] focus:border-[#76B900] rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-neutral-500 focus:outline-none font-mono"
                />
              </div>

              <div className="space-y-2">
                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full py-2.5 rounded-xl bg-gradient-to-r from-[#22c55e] to-[#16a34a] hover:from-[#16a34a] hover:to-[#15803d] text-white font-semibold text-xs flex items-center justify-center gap-2 transition-all cursor-pointer shadow-lg shadow-green-900/30"
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
                  className="w-full py-2 rounded-xl bg-[#1a1a1a] hover:bg-[#222] border border-[#333] text-xs font-mono text-neutral-300 hover:text-white flex items-center justify-center gap-2 transition-colors cursor-pointer"
                >
                  <Sparkles className="w-3.5 h-3.5 text-[#76B900]" />
                  <span>Instant Studio Access (Demo Mode)</span>
                </button>
              </div>
            </form>

            <div className="pt-2 border-t border-[#222] flex items-center justify-between text-[11px] font-mono text-neutral-500">
              <span className="flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5 text-[#76B900]" />
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
