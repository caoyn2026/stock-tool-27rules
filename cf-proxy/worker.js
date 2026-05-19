export default {
  async fetch(request) {
    const url = new URL(request.url);
    // 将请求转发到Vercel
    const vercelUrl = 'https://stock-tool-eight.vercel.app' + url.pathname + url.search;
    
    const newRequest = new Request(vercelUrl, {
      method: request.method,
      headers: request.headers,
      body: request.body,
    });
    
    const response = await fetch(newRequest);
    
    // 复制响应并添加CORS头
    const newResponse = new Response(response.body, response);
    newResponse.headers.set('Access-Control-Allow-Origin', '*');
    newResponse.headers.set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    newResponse.headers.set('Access-Control-Allow-Headers', 'Content-Type');
    
    return newResponse;
  }
};
