"use client";

import { createContext, useContext, useCallback, useRef, ReactNode } from "react";

interface NavigationContextValue {
  vehicleIds: number[];
  filterParams: string;
  currentPage: number;
  totalCount: number;
  getAdjacentIds: (currentId: number) => { prevId: number | null; nextId: number | null; index: number };
  getBackUrl: () => string;
  setVehicleList: (ids: number[], params: string, page: number, total: number) => void;
}

const NavigationContext = createContext<NavigationContextValue | null>(null);

const STORAGE_KEY = "auction-nav-context";

function loadFromSession(): { ids: number[]; params: string; page: number; total: number } {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return { ids: [], params: "", page: 1, total: 0 };
}

function saveToSession(ids: number[], params: string, page: number, total: number) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ ids, params, page, total }));
  } catch {}
}

export function NavigationProvider({ children }: { children: ReactNode }) {
  const stateRef = useRef(loadFromSession());

  const setVehicleList = useCallback((ids: number[], params: string, page: number, total: number) => {
    stateRef.current = { ids, params, page, total };
    saveToSession(ids, params, page, total);
  }, []);

  const getAdjacentIds = useCallback((currentId: number) => {
    const { ids } = stateRef.current;
    const index = ids.indexOf(currentId);
    if (index === -1) return { prevId: null, nextId: null, index: -1 };
    return {
      prevId: index > 0 ? ids[index - 1] : null,
      nextId: index < ids.length - 1 ? ids[index + 1] : null,
      index,
    };
  }, []);

  const getBackUrl = useCallback(() => {
    const { params } = stateRef.current;
    return params ? `/dashboard?${params}` : "/dashboard";
  }, []);

  const value: NavigationContextValue = {
    get vehicleIds() { return stateRef.current.ids; },
    get filterParams() { return stateRef.current.params; },
    get currentPage() { return stateRef.current.page; },
    get totalCount() { return stateRef.current.total; },
    getAdjacentIds,
    getBackUrl,
    setVehicleList,
  };

  return <NavigationContext value={value}>{children}</NavigationContext>;
}

export function useNavigationContext() {
  return useContext(NavigationContext);
}
