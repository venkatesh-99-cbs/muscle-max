import api from "./api";

export const askChatbot = (question) => api.post("/chatbot/ask/", { question });
