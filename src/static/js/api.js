/**
 * HealthCost AI Copilot - API Client
 *
 * Handles all communication with the FastAPI backend.
 */

const API_BASE = '/api/v1';

/**
 * Generic API request handler
 */
async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;

    const config = {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
        ...options,
    };

    // Remove Content-Type for FormData (browser sets it automatically with boundary)
    if (options.body instanceof FormData) {
        delete config.headers['Content-Type'];
    }

    try {
        const response = await fetch(url, config);

        if (!response.ok) {
            const error = await response.json().catch(() => ({
                detail: `HTTP error ${response.status}`
            }));
            throw new Error(error.detail || 'Erro na requisicao');
        }

        return await response.json();
    } catch (error) {
        console.error(`API Error [${endpoint}]:`, error);
        throw error;
    }
}

/**
 * Clients API
 */
const ClientsAPI = {
    /**
     * List all clients
     */
    async list(params = {}) {
        const query = new URLSearchParams(params).toString();
        return apiRequest(`/clients/${query ? '?' + query : ''}`);
    },

    /**
     * Get a specific client
     */
    async get(clientId) {
        return apiRequest(`/clients/${clientId}`);
    },

    /**
     * Create a new client
     */
    async create(data) {
        return apiRequest('/clients/', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },

    /**
     * Update a client
     */
    async update(clientId, data) {
        return apiRequest(`/clients/${clientId}`, {
            method: 'PATCH',
            body: JSON.stringify(data),
        });
    },

    /**
     * Delete a client
     */
    async delete(clientId, permanent = false) {
        return apiRequest(`/clients/${clientId}?permanent=${permanent}`, {
            method: 'DELETE',
        });
    },

    /**
     * Get client contracts
     */
    async getContracts(clientId, params = {}) {
        const query = new URLSearchParams(params).toString();
        return apiRequest(`/clients/${clientId}/contracts${query ? '?' + query : ''}`);
    },

    /**
     * Get client processing status
     */
    async getProcessingStatus(clientId) {
        return apiRequest(`/clients/${clientId}/processing-status`);
    },
};

/**
 * Conversations API
 */
const ConversationsAPI = {
    /**
     * List conversations for a client
     */
    async list(clientId, params = {}) {
        const query = new URLSearchParams({ client_id: clientId, ...params }).toString();
        return apiRequest(`/conversations/?${query}`);
    },

    /**
     * Get a specific conversation
     */
    async get(conversationId, clientId) {
        return apiRequest(`/conversations/${conversationId}?client_id=${clientId}`);
    },

    /**
     * Create a new conversation
     */
    async create(data) {
        return apiRequest('/conversations/', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },

    /**
     * Delete a conversation
     */
    async delete(conversationId, clientId) {
        return apiRequest(`/conversations/${conversationId}?client_id=${clientId}`, {
            method: 'DELETE',
        });
    },

    /**
     * Delete a specific message from a conversation
     */
    async deleteMessage(conversationId, messageId, clientId) {
        return apiRequest(`/conversations/${conversationId}/messages/${messageId}?client_id=${clientId}`, {
            method: 'DELETE',
        });
    },
};

/**
 * Chat API
 */
const ChatAPI = {
    /**
     * Send a message to the chat
     */
    async sendMessage(message, clientId, options = {}) {
        const data = {
            message,
            client_id: clientId,
            contract_id: options.contractId || null,
            conversation_id: options.conversationId || null,
            include_sources: options.includeSources !== false,
            include_debug: options.includeDebug || false,
        };

        return apiRequest('/chat/', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },

    /**
     * Send a simple message (no persistence)
     */
    async sendSimpleMessage(message, clientId, contractId = null) {
        const params = new URLSearchParams({
            message,
            client_id: clientId,
        });
        if (contractId) params.append('contract_id', contractId);

        return apiRequest(`/chat/simple?${params}`, {
            method: 'POST',
        });
    },

    /**
     * Send a message with streaming status updates (SSE)
     * @param {string} message - The message to send
     * @param {string} clientId - The client ID
     * @param {Object} options - Additional options
     * @param {Function} options.onStatus - Callback for status updates: (step, message, agent) => void
     * @param {Function} options.onComplete - Callback for completion: (response) => void
     * @param {Function} options.onError - Callback for errors: (error) => void
     * @returns {AbortController} Controller to abort the stream if needed
     */
    sendMessageStream(message, clientId, options = {}) {
        const data = {
            message,
            client_id: clientId,
            contract_id: options.contractId || null,
            conversation_id: options.conversationId || null,
            include_sources: options.includeSources !== false,
            include_debug: options.includeDebug || false,
        };

        const abortController = new AbortController();

        // Use fetch with POST for SSE (EventSource only supports GET)
        fetch(`${API_BASE}/chat/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream',
            },
            body: JSON.stringify(data),
            signal: abortController.signal,
        })
            .then(async (response) => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });

                    // Process complete SSE messages
                    const lines = buffer.split('\n');
                    buffer = lines.pop() || ''; // Keep incomplete line in buffer

                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const eventData = JSON.parse(line.slice(6));

                                if (eventData.event === 'status') {
                                    if (options.onStatus) {
                                        options.onStatus(
                                            eventData.data.step,
                                            eventData.data.message,
                                            eventData.data.agent
                                        );
                                    }
                                } else if (eventData.event === 'complete') {
                                    if (options.onComplete) {
                                        options.onComplete(eventData.data);
                                    }
                                } else if (eventData.event === 'error') {
                                    if (options.onError) {
                                        options.onError(eventData.data);
                                    }
                                }
                            } catch (e) {
                                console.warn('Failed to parse SSE event:', line, e);
                            }
                        }
                    }
                }
            })
            .catch((error) => {
                if (error.name !== 'AbortError') {
                    console.error('Stream error:', error);
                    if (options.onError) {
                        options.onError({ error: 'stream_error', message: error.message });
                    }
                }
            });

        return abortController;
    },
};

/**
 * Upload API
 */
const UploadAPI = {
    /**
     * Upload a contract PDF
     */
    async uploadContract(file, clientId, options = {}) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('client_id', clientId);
        if (options.contractId) {
            formData.append('contract_id', options.contractId);
        }

        return apiRequest('/upload/contract', {
            method: 'POST',
            body: formData,
        });
    },

    /**
     * Upload cost data (CSV/Excel)
     */
    async uploadCosts(file, clientId, options = {}) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('client_id', clientId);
        if (options.contractId) {
            formData.append('contract_id', options.contractId);
        }

        return apiRequest('/upload/costs', {
            method: 'POST',
            body: formData,
        });
    },

    /**
     * Upload with progress tracking
     */
    uploadWithProgress(file, clientId, type = 'contract', options = {}) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            const formData = new FormData();

            formData.append('file', file);
            formData.append('client_id', clientId);
            if (options.contractId) {
                formData.append('contract_id', options.contractId);
            }

            const endpoint = type === 'contract' ? '/upload/contract' : '/upload/costs';

            xhr.open('POST', `${API_BASE}${endpoint}`);

            // Progress handler
            xhr.upload.onprogress = (event) => {
                if (event.lengthComputable && options.onProgress) {
                    const percent = Math.round((event.loaded / event.total) * 100);
                    options.onProgress(percent, event.loaded, event.total);
                }
            };

            // Completion handler
            xhr.onload = () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        resolve(response);
                    } catch (e) {
                        reject(new Error('Erro ao processar resposta'));
                    }
                } else {
                    try {
                        const error = JSON.parse(xhr.responseText);
                        reject(new Error(error.detail || 'Erro no upload'));
                    } catch (e) {
                        reject(new Error(`HTTP error ${xhr.status}`));
                    }
                }
            };

            // Error handler
            xhr.onerror = () => {
                reject(new Error('Erro de rede'));
            };

            // Abort handler
            xhr.onabort = () => {
                reject(new Error('Upload cancelado'));
            };

            xhr.send(formData);

            // Return abort function
            if (options.getAbortController) {
                options.getAbortController({ abort: () => xhr.abort() });
            }
        });
    },
};

/**
 * Documents API
 */
const DocumentsAPI = {
    /**
     * List documents
     */
    async list(clientId, params = {}) {
        const query = new URLSearchParams({ client_id: clientId, ...params }).toString();
        return apiRequest(`/documents/?${query}`);
    },

    /**
     * Get document details
     */
    async get(documentId, clientId) {
        return apiRequest(`/documents/${documentId}?client_id=${clientId}`);
    },

    /**
     * Get document status
     */
    async getStatus(documentId) {
        return apiRequest(`/documents/${documentId}/status`);
    },

    /**
     * Process a contract document (PDF)
     * Extracts text, creates chunks, generates embeddings, indexes in Azure AI Search
     */
    async process(documentId, clientId) {
        return apiRequest('/documents/process', {
            method: 'POST',
            body: JSON.stringify({
                document_id: documentId,
                client_id: clientId,
            }),
        });
    },

    /**
     * Reprocess a document
     */
    async reprocess(documentId, clientId) {
        return apiRequest(`/documents/${documentId}/reprocess?client_id=${clientId}`, {
            method: 'POST',
        });
    },
};

/**
 * Costs API
 */
const CostsAPI = {
    /**
     * Process a cost document (CSV/Excel)
     * Parses rows, validates data, stores in Cosmos DB
     */
    async process(documentId, clientId) {
        return apiRequest('/costs/process', {
            method: 'POST',
            body: JSON.stringify({
                document_id: documentId,
                client_id: clientId,
            }),
        });
    },

    /**
     * Get cost records
     */
    async getRecords(clientId, params = {}) {
        const query = new URLSearchParams({ client_id: clientId, ...params }).toString();
        return apiRequest(`/costs/records?${query}`);
    },

    /**
     * Get cost summary
     */
    async getSummary(clientId, contractId = null) {
        const params = { client_id: clientId };
        if (contractId) params.contract_id = contractId;
        const query = new URLSearchParams(params).toString();
        return apiRequest(`/costs/summary?${query}`);
    },
};

// Export for global use
window.API = {
    Clients: ClientsAPI,
    Conversations: ConversationsAPI,
    Chat: ChatAPI,
    Upload: UploadAPI,
    Documents: DocumentsAPI,
    Costs: CostsAPI,
};
