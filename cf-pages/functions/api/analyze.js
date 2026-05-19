export async function onRequestGet(context) {
  const url = new URL(context.request.url);
  const code = url.searchParams.get('code') || '';
  const vercelUrl = `https://stock-tool-eight.vercel.app/api/analyze?code=${encodeURIComponent(code)}`;
  
  try {
    const controller = new AbortController();
    // akshare获取数据可能需要较长时间，给60秒
    const timeout = setTimeout(() => controller.abort(), 60000);
    
    const response = await fetch(vercelUrl, { signal: controller.signal });
    clearTimeout(timeout);
    
    const text = await response.text();
    
    // 检查是否返回了HTML（Vercel超时/错误页）
    if (text.trim().startsWith('<!') || text.trim().startsWith('<html') || text.trim().startsWith('<HTML')) {
      return new Response(JSON.stringify({ 
        error: '数据获取超时，该股票数据源响应过慢。请换一只股票或稍后重试。' 
      }), {
        status: 502,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      });
    }
    
    return new Response(text, {
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
  } catch (e) {
    let msg = '网络错误，请稍后重试';
    if (e.name === 'AbortError') {
      msg = '数据获取超时（60秒），该股票数据源响应过慢。请换一只股票或稍后重试。';
    }
    return new Response(JSON.stringify({ error: msg }), {
      status: 504,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
  }
}
