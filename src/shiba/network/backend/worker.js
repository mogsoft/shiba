export default {
    async fetch(request, env) {
        if (request.method !== 'POST') {
            return new Response('Method not allowed', { status: 405 });
        }

        const { username, password } = await request.json();

        // 1. Validate incoming credentials against your user database or secrets
        if (username !== env.APP_USER || password !== env.APP_PASSWORD) {
            return new Response(JSON.stringify({ error: 'Invalid credentials' }), {
                status: 401,
                headers: { 'Content-Type': 'application/json' }
            });
        }

        // 2. Request a temporary/scoped token from Cloudflare REST API
        const cfAccountId = env.CF_ACCOUNT_ID;
        const cfApiToken = env.CF_MASTER_API_TOKEN;

        const cfResponse = await fetch(
            `https://api.cloudflare.com/client/v4/accounts/${cfAccountId}/r2/buckets/${env.BUCKET_NAME}/tokens`,
            {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${cfApiToken}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    ttl: 3600, // Token lifetime in seconds (1 hour)
                    permission: 'object-read-write'
                })
            }
        );

        const tokenData = await cfResponse.json();

        if (!tokenData.success) {
            return new Response(JSON.stringify({ error: 'Failed to generate S3 keys' }), { status: 500 });
        }

        // 3. Return the S3 credentials in the response payload
        return new Response(JSON.stringify({
            access_key_id: tokenData.result.accessKeyId,
            secret_access_key: tokenData.result.secretAccessKey,
            endpoint_url: `https://${cfAccountId}.r2.cloudflarestorage.com`,
            expires_in: 3600
        }), {
            headers: { 'Content-Type': 'application/json' }
        });
    }
};