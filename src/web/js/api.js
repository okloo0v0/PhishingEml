const jsonHeaders = { Accept: 'application/json' };

async function request(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { ...jsonHeaders, ...(options.headers || {}) } });
  const body = await response.json().catch(() => ({ success: false, error: { message: '服务返回了无效响应' } }));
  if (!response.ok || body.success === false) {
    const error = new Error(body.error?.message || `请求失败（${response.status}）`);
    error.code = body.error?.code || 'HTTP_ERROR';
    error.status = response.status;
    throw error;
  }
  return body.data;
}

export function health() { return request('/health'); }
export function analyzeFile(file) { const data = new FormData(); data.append('file', file); return request('/api/emails/analyze', { method: 'POST', body: data }); }
export function analyzeText(rawText) { const data = new FormData(); data.append('raw_text', rawText); return request('/api/emails/analyze', { method: 'POST', body: data }); }
export function analyzeSample(sampleId) { const data = new FormData(); data.append('sample_id', sampleId); return request('/api/emails/analyze', { method: 'POST', body: data }); }
export function listDetections(riskLevel = '') { const query = new URLSearchParams({ page: '1', page_size: '50' }); if (riskLevel) query.set('risk_level', riskLevel); return request(`/api/detections?${query}`); }
export function detectionDetail(id) { return request(`/api/detections/${encodeURIComponent(id)}`); }
export function deleteDetection(id) { return request(`/api/detections/${encodeURIComponent(id)}`, { method: 'DELETE' }); }
export function listBlacklist(keyword = '', status = '') { const query = new URLSearchParams({ page: '1', page_size: '100' }); if (keyword) query.set('keyword', keyword); if (status) query.set('status', status); return request(`/api/blacklist?${query}`); }
export function createBlacklist(payload) { return request('/api/blacklist', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); }
export function updateBlacklist(id, payload) { return request(`/api/blacklist/${encodeURIComponent(id)}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); }
export function overview() { return request('/api/statistics/overview'); }
export function modelMetrics() { return request('/api/model/metrics'); }
export function knowledge(params = {}) { const query = new URLSearchParams(); if (params.keyword) query.set('keyword', params.keyword); if (params.category) query.set('category', params.category); return request(`/api/knowledge${query.toString() ? `?${query}` : ''}`); }
export function feedback(payload) { return request('/api/feedback', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); }
