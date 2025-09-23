### A Nexus guardian? Tide-weaver??

# What The Chess??!?!

What The Chess is a unique, multiplayer spin on chess, and also our BigRed//Hacks 2025 submission. Both player's recieve the same set of **AI generated pieces**, with their own unique names and rules for moving/capturing across the board. We generate pieces and their rulesets using Google's Gemini API, making the chance of getting the same pieces in different matches near zero.

The visuals aren't the best due to the lack of time. 

## Running

The project uses `uv` for venv management. To get started, run `uv sync` in the project directory.

- To run the server: `uv run -m server.main`
- To run the client: `uv run -m client.main`

The client accepts an optional IP argument as the first cmd-line argument. Without it, the server IP defaults to localhost.

The server accepts an optional Gemini API key as the first cmd-line argument. Without it, the server attempts to use the GOOGLE_API_KEY env variable. 

## Contributors

- [@zhn2605](https://github.com/zhn2605)
- [@alias1233](https://github.com/alias1233)
- [@nioii](https://github.com/nioii)

