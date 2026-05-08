import time

class BenchmarkMetrics:
    def __init__(self, mode, task):
        self.mode = mode
        self.task = task
        self.steps = 0
        self.tokens_in = 0 # Incremental (what was actually evaluated)
        self.tokens_out = 0
        self.total_context_tokens = 0 # Peak context size
        self.cumulative_cost_tokens = 0 # Sum of full context size per step
        self.latency_ms = 0
        self.start_time = time.time()
        self.end_time = 0
        self.success = False
        self.summary = ""
        self.nudges = 0
        
    def add_step(self, tokens_in, tokens_out, latency_ms, context_size):
        self.steps += 1
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        self.latency_ms += latency_ms
        self.total_context_tokens = max(self.total_context_tokens, context_size)
        self.cumulative_cost_tokens += context_size

    def add_nudge(self):
        self.nudges += 1
        
    def finish(self, success, summary):
        self.end_time = time.time()
        self.success = success
        self.summary = summary
        
    def render_report(self):
        print("\n" + "="*80)
        print(f" FINAL BENCHMARK REPORT | MODE: {self.mode.upper()}")
        print("="*80)
        print(f"Success           | {self.success}")
        print(f"Summary           | {self.summary}")
        print(f"Steps             | {self.steps}")
        print(f"Nudges            | {self.nudges}")
        print(f"Tokens In (Eval)  | {self.tokens_in} (Actual compute effort)")
        print(f"Total Context     | {self.total_context_tokens} (Max pressure)")
        print(f"Cumulative Cost   | {self.cumulative_cost_tokens} (As if no caching)")
        print(f"Tokens Out        | {self.tokens_out}")
        print(f"Duration (s)      | {self.end_time - self.start_time:.2f}")
        
        # Cost Analysis Sektion
        print("\n" + "-"*40)
        print(" 💰 ESTIMATED COST ANALYSIS (USD)")
        print("-"*40)
        prices = {
            "Gemini 3.1 Flash-Lite": (0.25, 1.50),
            "Gemini 3.1 Pro":        (2.00, 12.00),
            "GPT-5.4 mini":          (0.75, 4.50),
            "GPT-5.5 / Claude Opus": (5.00, 30.00),
        }
        
        print(f"{'Model':<25} | {'Cost':<10}")
        print("-" * 40)
        for model, (p_in, p_out) in prices.items():
            cost = (self.tokens_in / 1_000_000 * p_in) + (self.tokens_out / 1_000_000 * p_out)
            print(f"{model:<25} | ${cost:.6f}")
        print("="*80)
