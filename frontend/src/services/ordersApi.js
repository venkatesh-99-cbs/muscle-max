import api from "./api";

export const createOrder = (payload) => api.post("/orders/", payload);
export const listOrders = () => api.get("/orders/");
