import React from 'react';

/**
 * EchoOrb — Soft glowing SVG/CSS gradient orb avatar.
 * Zero external heavy assets; responsive to style tints and interactive states.
 */
export default function EchoOrb({
  size = 'md',
  style = 'default', // 'rational' | 'emotional' | 'ambitious' | 'default'
  state = 'idle',   // 'idle' | 'thinking' | 'speaking' | 'evolving'
  className = '',
  onClick,
  title = 'Echo'
}) {
  const sizeMap = {
    xs: 'w-5 h-5',
    sm: 'w-8 h-8',
    md: 'w-11 h-11',
    lg: 'w-20 h-20',
    xl: 'w-32 h-32',
    hero: 'w-48 h-48 sm:w-64 sm:h-64'
  };

  // Color schemes based on thinking style
  const gradients = {
    rational: {
      stop1: '#2EC4B6',
      stop2: '#20A495',
      glow: 'rgba(46, 196, 182, 0.45)',
      ring: 'rgba(46, 196, 182, 0.25)'
    },
    emotional: {
      stop1: '#FF8FA3',
      stop2: '#FF5C7E',
      glow: 'rgba(255, 143, 163, 0.45)',
      ring: 'rgba(255, 143, 163, 0.25)'
    },
    ambitious: {
      stop1: '#8B5CF6',
      stop2: '#FF9F43',
      glow: 'rgba(139, 92, 246, 0.45)',
      ring: 'rgba(255, 159, 67, 0.25)'
    },
    default: {
      stop1: '#7C5CFF',
      stop2: '#FF7A9E',
      glow: 'rgba(124, 92, 255, 0.45)',
      ring: 'rgba(255, 122, 158, 0.25)'
    }
  };

  const currentGradient = gradients[style] || gradients.default;
  const isThinking = state === 'thinking';
  const isEvolving = state === 'evolving';

  return (
    <div
      onClick={onClick}
      title={title}
      aria-label={`${title} avatar`}
      className={`relative flex items-center justify-center select-none ${sizeMap[size] || sizeMap.md} ${className} ${onClick ? 'cursor-pointer hover:scale-105 transition-transform' : ''}`}
      style={{
        filter: `drop-shadow(0 0 20px ${currentGradient.glow})`,
      }}
    >
      {/* Outer ambient blur halo */}
      <div
        className="absolute inset-0 rounded-full blur-xl opacity-60 transition-all duration-700 pointer-events-none"
        style={{
          background: `radial-gradient(circle, ${currentGradient.stop1} 0%, ${currentGradient.stop2} 100%)`,
        }}
      />

      {/* Orbiting ring when thinking or evolving */}
      {(isThinking || isEvolving) && (
        <div
          className="absolute -inset-1.5 rounded-full border border-dashed animate-spin pointer-events-none"
          style={{
            borderColor: currentGradient.stop1,
            animationDuration: isThinking ? '3s' : '1.5s',
            opacity: 0.7
          }}
        />
      )}

      {/* Main Vector Orb with Multi-stop Spherical Lighting */}
      <svg
        viewBox="0 0 100 100"
        className={`w-full h-full relative z-10 ${state === 'idle' ? 'animate-orb-breathe' : ''} ${isThinking ? 'animate-pulse' : ''}`}
      >
        <defs>
          {/* Base Sphere Gradient */}
          <radialGradient id={`orbGrad-${style}`} cx="35%" cy="30%" r="70%">
            <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.8" />
            <stop offset="25%" stopColor={currentGradient.stop1} stopOpacity="0.95" />
            <stop offset="75%" stopColor={currentGradient.stop2} stopOpacity="0.9" />
            <stop offset="100%" stopColor="#1B1530" stopOpacity="0.6" />
          </radialGradient>

          {/* Inner Light Glow */}
          <linearGradient id={`innerGlow-${style}`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.6" />
            <stop offset="100%" stopColor="transparent" stopOpacity="0" />
          </linearGradient>

          {/* Core Energy Filter */}
          <filter id="coreGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Outer sphere body */}
        <circle
          cx="50"
          cy="50"
          r="46"
          fill={`url(#orbGrad-${style})`}
          filter="url(#coreGlow)"
          className="transition-all duration-700"
        />

        {/* Top reflection highlight */}
        <ellipse
          cx="38"
          cy="30"
          rx="18"
          ry="11"
          fill="url(#innerGlow-default)"
          transform="rotate(-25 38 30)"
          className="opacity-75"
        />

        {/* Pulsing Core Center */}
        <circle
          cx="50"
          cy="50"
          r="10"
          fill="#FFFFFF"
          className={`opacity-40 ${isThinking ? 'animate-ping' : ''}`}
        />
      </svg>
    </div>
  );
}
