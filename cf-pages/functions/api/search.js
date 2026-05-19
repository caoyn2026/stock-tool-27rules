export async function onRequestGet(context) {
  const url = new URL(context.request.url);
  const q = url.searchParams.get('q') || '';
  const vercelUrl = `https://stock-tool-eight.vercel.app/api/search?q=${encodeURIComponent(q)}`;
  
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    
    const response = await fetch(vercelUrl, { signal: controller.signal });
    clearTimeout(timeout);
    
    const text = await response.text();
    
    // 检查是否返回了HTML（Vercel错误页）
    if (text.trim().startsWith('<!') || text.trim().startsWith('<html')) {
      return new Response(JSON.stringify({ error: '服务器暂时不可用，请稍后重试' }), {
        status: 502,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      });
    }
    
    return new Response(text, {
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
  } catch (e) {
    const msg = e.name === 'AbortError' ? '请求超时，请稍后重试' : '网络错误，请稍后重试';
    return new Response(JSON.stringify({ error: msg }), {
      status: 504,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
  }
}
