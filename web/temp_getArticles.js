  getArticles: async(params = {}) => {
    try {
      const response = await api.get('/api/articles/', { params });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch articles:', error);
      throw error;
    }
  },
