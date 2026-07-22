import { useCallback, useEffect, useState } from 'react';
import { ApiError } from '@/src/services/api/apiClient';

interface AsyncDataState<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
  /** HTTP status code of the last error, when it came from our API (e.g. 404), else null. */
  errorStatus: number | null;
  refetch: () => void;
}

/**
 * Generic data-fetching hook used across screens to fetch from a
 * Repository and expose consistent loading/error/empty state handling.
 */
export function useAsyncData<T>(fetchFn: () => Promise<T>, deps: unknown[] = []): AsyncDataState<T> {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [refetchToken, setRefetchToken] = useState(0);

  useEffect(() => {
    let isCancelled = false;
    setIsLoading(true);
    setError(null);
    setErrorStatus(null);

    fetchFn()
      .then((result) => {
        if (!isCancelled) setData(result);
      })
      .catch((err) => {
        if (!isCancelled) {
          setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.');
          setErrorStatus(err instanceof ApiError ? err.status : null);
        }
      })
      .finally(() => {
        if (!isCancelled) setIsLoading(false);
      });

    return () => {
      isCancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, refetchToken]);

  const refetch = useCallback(() => setRefetchToken((t) => t + 1), []);

  return { data, isLoading, error, errorStatus, refetch };
}
