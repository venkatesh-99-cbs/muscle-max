import api from "./api";

export const getCart = () => api.get("/cart/");
export const addToCart = (productId, quantity = 1) =>
  api.post("/cart/items/", { product: productId, quantity });
