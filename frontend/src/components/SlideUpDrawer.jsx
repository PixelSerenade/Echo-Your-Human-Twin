import React, { useEffect } from 'react';
import { X } from 'lucide-react';

/**
 * SlideUpDrawer — Accessible slide-up bottom sheet for mobile and focused drawer for desktop.
 * Keeps secondary tasks (Why?, Debate, Audit Log, Modifier learning) from cluttering primary views.
 */
export default function SlideUpDrawer({
  isOpen,
  onClose,
  title,
  subtitle,
  badge,
  children,
  maxWidth = 'max-w-2xl'
}) {
  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Lock body scroll when drawer is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4">
      {/* Backdrop with soft blur */}
      <div
        onClick={onClose}
        className="fixed inset-0 bg-[#120F1C]/60 dark:bg-[#0A0714]/80 backdrop-blur-md transition-opacity animate-fadeIn cursor-pointer"
      />

      {/* Drawer Container */}
      <div
        className={`relative z-10 w-full ${maxWidth} bg-white dark:bg-[#1D1830] border-t sm:border border-stroke-light dark:border-stroke-dark rounded-t-3xl sm:rounded-3xl shadow-2xl overflow-hidden max-h-[90vh] flex flex-col animate-pop`}
      >
        {/* Mobile Pull Handle */}
        <div className="sm:hidden flex justify-center pt-3 pb-1">
          <div className="w-12 h-1.5 bg-stroke-light dark:bg-stroke-dark rounded-full" />
        </div>

        {/* Header */}
        <div className="px-6 py-4 border-b border-stroke-light dark:border-stroke-dark flex items-center justify-between">
          <div className="space-y-0.5">
            <div className="flex items-center space-x-2">
              <h3 className="text-lg font-bold font-heading text-content-mainLight dark:text-content-mainDark">
                {title}
              </h3>
              {badge && (
                <span className="text-xs px-2.5 py-0.5 rounded-full font-medium bg-surface-subtleLight dark:bg-surface-subtleDark text-brand-purple dark:text-[#A894FF] border border-stroke-light dark:border-stroke-dark">
                  {badge}
                </span>
              )}
            </div>
            {subtitle && (
              <p className="text-xs text-content-mutedLight dark:text-content-mutedDark">
                {subtitle}
              </p>
            )}
          </div>

          <button
            onClick={onClose}
            aria-label="Close"
            className="w-9 h-9 rounded-full flex items-center justify-center text-content-mutedLight dark:text-content-mutedDark hover:bg-surface-subtleLight dark:hover:bg-surface-subtleDark hover:text-content-mainLight dark:hover:text-content-mainDark transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Content Body */}
        <div className="px-6 py-5 overflow-y-auto space-y-4 flex-1">
          {children}
        </div>
      </div>
    </div>
  );
}
