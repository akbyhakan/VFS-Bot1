import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/services/api';
import type {
  AppointmentRequest,
  AppointmentRequestResponse,
  Country,
} from '@/types/appointment';

// Query to get all countries
export function useCountries() {
  return useQuery<Country[]>({
    queryKey: ['countries'],
    queryFn: () => api.get<Country[]>('/api/countries'),
    staleTime: 3600000, // 1 hour - countries don't change often
  });
}

// Query to get centres for a specific country
export function useCentres(countryCode: string) {
  return useQuery<string[]>({
    queryKey: ['centres', countryCode],
    queryFn: () => api.get<string[]>(`/api/countries/${countryCode}/centres`),
    enabled: !!countryCode, // Only run if countryCode is provided
    staleTime: 3600000, // 1 hour
  });
}

// Query to get categories for a specific centre
export function useCategories(countryCode: string, centreName: string) {
  return useQuery<string[]>({
    queryKey: ['categories', countryCode, centreName],
    queryFn: () => api.get<string[]>(`/api/countries/${countryCode}/centres/${encodeURIComponent(centreName)}/categories`),
    enabled: !!countryCode && !!centreName,
    staleTime: 3600000, // 1 hour
  });
}

// Query to get subcategories for a specific centre and category
export function useSubcategories(countryCode: string, centreName: string, categoryName: string) {
  return useQuery<string[]>({
    queryKey: ['subcategories', countryCode, centreName, categoryName],
    queryFn: () => api.get<string[]>(`/api/countries/${countryCode}/centres/${encodeURIComponent(centreName)}/categories/${encodeURIComponent(categoryName)}/subcategories`),
    enabled: !!countryCode && !!centreName && !!categoryName,
    staleTime: 3600000, // 1 hour
  });
}

// Query to get all appointment requests
export function useAppointmentRequests(status?: string) {
  return useQuery<AppointmentRequestResponse[]>({
    queryKey: ['appointment-requests', status],
    queryFn: () => {
      const url = status
        ? `/api/appointment-requests?status=${status}`
        : '/api/appointment-requests';
      return api.get<AppointmentRequestResponse[]>(url);
    },
    refetchInterval: 10000, // Refresh every 10 seconds
  });
}

// Query to get a single appointment request
export function useAppointmentRequest(requestId: number) {
  return useQuery<AppointmentRequestResponse>({
    queryKey: ['appointment-request', requestId],
    queryFn: () => api.get<AppointmentRequestResponse>(`/api/appointment-requests/${requestId}`),
    enabled: !!requestId,
  });
}

// Mutation to create a new appointment request
export function useCreateAppointmentRequest() {
  const queryClient = useQueryClient();
  return useMutation<
    { id: number; status: string; message: string },
    Error,
    AppointmentRequest
  >({
    mutationFn: (data) => api.post('/api/appointment-requests', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointment-requests'] });
    },
  });
}

// Mutation to delete an appointment request
export function useDeleteAppointmentRequest() {
  const queryClient = useQueryClient();
  return useMutation<{ success: boolean; message: string }, Error, number>({
    mutationFn: (requestId) => api.delete(`/api/appointment-requests/${requestId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointment-requests'] });
    },
  });
}

// Mutation to update appointment request status
export function useUpdateAppointmentRequestStatus() {
  const queryClient = useQueryClient();
  return useMutation<
    { success: boolean; message: string },
    Error,
    { requestId: number; status: string }
  >({
    mutationFn: ({ requestId, status }) =>
      api.patch(`/api/appointment-requests/${requestId}/status`, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointment-requests'] });
    },
  });
}
