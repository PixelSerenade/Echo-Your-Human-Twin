import React, { createContext, useContext, useState, useEffect } from 'react';

const ThemeContext = createContext();

export function ThemeProvider({ children }) {
  // Theme mode: 'system' | 'light' | 'dark'
  const [theme, setThemeState] = useState(() => {
    if (typeof window !== 'undefined') {
      const qTheme = new URLSearchParams(window.location.search).get('theme');
      if (qTheme === 'light' || qTheme === 'dark') return qTheme;
      return localStorage.getItem('humantwin_theme') || 'dark';
    }
    return 'dark';
  });

  const [effectiveTheme, setEffectiveTheme] = useState('dark');

  // Reduce motion preference
  const [reduceMotion, setReduceMotionState] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('humantwin_reduce_motion');
      if (saved !== null) return saved === 'true';
      return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }
    return false;
  });

  // Customizable Twin Name (default 'Echo')
  const [twinName, setTwinNameState] = useState('Echo');

  // Twin Thinking Style ('rational' | 'emotional' | 'ambitious' | 'default')
  const [twinStyle, setTwinStyleState] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('humantwin_twin_style') || 'rational';
    }
    return 'rational';
  });

  // Current active view: 'landing' | 'chat' | 'plan' | 'privacy' | 'twin' | 'settings'
  const [activePage, setActivePage] = useState(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const tab = params.get('tab');
      if (tab === 'simulator') return 'plan';
      if (tab === 'privacy') return 'privacy';
      if (tab === 'knowledge' || tab === 'twin') return 'twin';
      if (tab === 'landing') return 'landing';
      if (tab === 'settings') return 'settings';
      if (tab === 'plan') return 'plan';
      if (tab === 'chat') return 'chat';
    }
    return 'chat';
  });

  // Apply theme to DOM
  useEffect(() => {
    const root = document.documentElement;
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

    const applyTheme = () => {
      let isDark = false;
      if (theme === 'system') {
        isDark = mediaQuery.matches;
      } else {
        isDark = theme === 'dark';
      }

      setEffectiveTheme(isDark ? 'dark' : 'light');
      if (isDark) {
        root.classList.add('dark');
      } else {
        root.classList.remove('dark');
      }
    };

    applyTheme();
    mediaQuery.addEventListener('change', applyTheme);
    return () => mediaQuery.removeEventListener('change', applyTheme);
  }, [theme]);

  // Apply reduce motion class
  useEffect(() => {
    const root = document.documentElement;
    if (reduceMotion) {
      root.classList.add('reduce-motion');
    } else {
      root.classList.remove('reduce-motion');
    }
  }, [reduceMotion]);

  const setTheme = (newTheme) => {
    setThemeState(newTheme);
    localStorage.setItem('humantwin_theme', newTheme);
  };

  const setReduceMotion = (val) => {
    setReduceMotionState(val);
    localStorage.setItem('humantwin_reduce_motion', val.toString());
  };

  const setTwinName = (name) => {
    setTwinNameState(String(name || '').trim() || 'Echo');
    localStorage.removeItem('humantwin_twin_name');
  };

  const setTwinStyle = (style) => {
    setTwinStyleState(style);
    localStorage.setItem('humantwin_twin_style', style);
  };

  return (
    <ThemeContext.Provider
      value={{
        theme,
        effectiveTheme,
        setTheme,
        reduceMotion,
        setReduceMotion,
        twinName,
        setTwinName,
        twinStyle,
        setTwinStyle,
        activePage,
        setActivePage,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
