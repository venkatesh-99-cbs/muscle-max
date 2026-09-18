import api from "./api";

export const listProducts = (params) => api.get("/products/", { params });
export const getProduct = (id) => api.get(`/products/${id}/`);
