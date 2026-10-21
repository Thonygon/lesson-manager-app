import { createContext, type PropsWithChildren, useCallback, useContext, useMemo, useState } from 'react';

type HomeIntroState = { requested: boolean; readyRoute: string | null };
type HomeIntroValue = HomeIntroState & {
  start: () => void;
  cancel: () => void;
  markReady: (route: string, ready: boolean) => void;
};

const HomeIntroContext = createContext<HomeIntroValue | null>(null);

export function HomeIntroProvider({ children }: PropsWithChildren) {
  const [state, setState] = useState<HomeIntroState>({ requested: false, readyRoute: null });
  const start = useCallback(() => setState({ requested: true, readyRoute: null }), []);
  const cancel = useCallback(() => setState({ requested: false, readyRoute: null }), []);
  const markReady = useCallback((route: string, ready: boolean) => {
    setState((current) => {
      const readyRoute = ready ? route : current.readyRoute === route ? null : current.readyRoute;
      return current.readyRoute === readyRoute ? current : { ...current, readyRoute };
    });
  }, []);
  const value = useMemo(() => ({ ...state, start, cancel, markReady }), [state, start, cancel, markReady]);
  return <HomeIntroContext.Provider value={value}>{children}</HomeIntroContext.Provider>;
}

export function useHomeIntro() {
  const value = useContext(HomeIntroContext);
  if (!value) throw new Error('useHomeIntro must be used inside HomeIntroProvider.');
  return value;
}
