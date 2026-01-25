import api from './api';

export const webhookApi = {
  /**
   * Create a webhook for a user
   */
  createWebhook: async (userId: number) => {
    const response = await api.post(`/api/webhook/users/${userId}/create`);
    return response.data;
  },

  /**
   * Get webhook information for a user
   */
  getWebhook: async (userId: number) => {
    const response = await api.get(`/api/webhook/users/${userId}`);
    return response.data;
  },

  /**
   * Delete a user's webhook
   */
  deleteWebhook: async (userId: number) => {
    const response = await api.delete(`/api/webhook/users/${userId}`);
    return response.data;
  },
};
