import { useEffect, useState } from "react"

/** Load one API resource; `error` holds a short message, never a stack. */
export function useData<T>(load: () => Promise<T>) {
  const [state, setState] = useState<{ data?: T; error?: string }>({})
  useEffect(() => {
    let live = true
    load()
      .then((data) => live && setState({ data }))
      .catch((error: unknown) => live && setState({ error: error instanceof Error ? error.message : "request failed" }))
    return () => {
      live = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return state
}
