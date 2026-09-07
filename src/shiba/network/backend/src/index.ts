import { WorkerEntrypoint } from "cloudflare:workers";

export default class extends WorkerEntrypoint<Env> {

  async get_user_secret(username: string): Promise<Response> {
	  try {
		  const value = await this.env.TOOLVIPER_KV.get(username, "text")
		  return new Response({value: value});
	  } catch (e) {
		  console.log("There was an error with your request: {e}");
		  return new Response(e.message, {status: 500});
	  }
  }

//  async set_user_secret(username: string, secret: string){
//	  try {
//		  await this.env.TOOLVIPER_KV.set(username, secret, {expeirationTtl: 120});
//	  } catch (e) {
//		  console.log("There was an error with your request: {e}");
//		  return new Response(e.message, {status: 500});
//	  }
//  }


  async process_file_request(request: Request, key: string, api_secret: Env){
      const trimmed_key = decodeURIComponent(key.replace("/^\/+/g", ""));

	  switch (request.method) {
      case "PUT": {
        await this.env.PUBLIC_DATA.put(trimmed_key, request.body, {
          onlyIf: request.headers,
          httpMetadata: request.headers,
        });

        return new Response(`Put ${key} successfully!`);
      }

      case "GET": {
        const object = await this.env.PUBLIC_DATA.get(key, {
          onlyIf: request.headers,
          range: request.headers,
        });

        if (object === null) {
          return new Response("Object Not Found", { status: 404 });
        }

        const headers = new Headers();
        object.writeHttpMetadata(headers);

        headers.set("etag", object.httpEtag);

        // When no body is present, preconditions have failed
        return new Response("body" in object ? object.body : undefined, {
          status: "body" in object ? 200 : 412,
          headers,
        });
      }
      case "DELETE": {
        await this.env.PUBLIC_DATA.delete(key);
        return new Response("Deleted!");
      }
      default:
        return new Response("Method Not Allowed", {
          status: 405,
          headers: {
            Allow: "PUT, GET, DELETE",
          },
        });
    }

  }

  async fetch(request: Request) {
    const url = new URL(request.url);
	const [_, secret, option, ...values] = url.pathname.split("/");
	const secret_ = await this.env.API_ADMIN_SECRET.get();

	  if (secret == secret_){
		  if (option == "kv") {

			  const [type, username] = values;
			  return new Response(JSON.stringify({"username": username}));

		  } else if (option == "file"){
			  const [key] = values;
			  return this.process_file_request(request, key, secret);
		  } else{
			  return new Response("Unknown operation ...");
		  }
	  } else {
		  return new Response("Invalid credentials ... ");
	  }
  }
};
