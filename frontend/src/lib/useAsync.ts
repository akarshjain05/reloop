import { useCallback, useEffect, useRef, useState } from "react";

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [state, setState] = useState<{ data?: T; error?: Error; loading: boolean }>({ loading: true });
  
  const fnRef = useRef(fn);
  fnRef.current = fn;
  
  const reqId = useRef(0);
  
  const run = useCallback(() => {
    const id = ++reqId.current;
    setState((s) => ({ data: s.data, loading: true }));
    fnRef.current().then(
      (data) => id === reqId.current && setState({ data, loading: false }),
      (error) => id === reqId.current && setState({ loading: false, error }),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  
  useEffect(() => {
    run();
  }, [run]);
  
  return { ...state, reload: run };
}
