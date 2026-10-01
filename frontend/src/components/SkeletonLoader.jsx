import React from 'react';

/**
 * SkeletonLoader — Soft shimmering placeholder loaders.
 * Replaces harsh spinners with airy, modern loading states.
 */
export default function SkeletonLoader({
  lines = 3,
  hasAvatar = false,
  className = ''
}) {
  return (
    <div className={`space-y-3 animate-pulse ${className}`}>
      <div className="flex items-center space-x-3">
        {hasAvatar && (
          <div className="w-10 h-10 rounded-full bg-surface-subtleLight dark:bg-surface-subtleDark flex-shrink-0" />
        )}
        <div className="space-y-2 flex-1">
          <div className="h-4 bg-surface-subtleLight dark:bg-surface-subtleDark rounded-full w-1/3" />
          <div className="h-3 bg-surface-subtleLight dark:bg-surface-subtleDark rounded-full w-2/3" />
        </div>
      </div>

      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="h-3.5 bg-surface-subtleLight dark:bg-surface-subtleDark rounded-full"
          style={{ width: `${95 - i * 14}%` }}
        />
      ))}
    </div>
  );
}
