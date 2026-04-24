import os
from typing import Any, Dict, List, Optional, Tuple, Union

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    StoppingCriteria,
    StoppingCriteriaList,
)


def is_ollama_model(model_name: str) -> bool:
    return model_name.startswith("ollama/")


def get_ollama_model_name(model_name: str) -> str:
    if is_ollama_model(model_name):
        return model_name.split("/", 1)[1]
    return model_name


def is_openai_compatible_model(model_name: str) -> bool:
    return model_name.startswith("openai/")


def get_openai_model_name(model_name: str) -> str:
    if is_openai_compatible_model(model_name):
        return model_name.split("/", 1)[1]
    return model_name


def make_model(eos: list, model_name: str, device: str, max_length: int, llm_cfg=None):
    if is_ollama_model(model_name):
        return None
    if is_openai_compatible_model(model_name):
        cfg = llm_cfg or {}
        return OpenAIChatModel(
            model_name=get_openai_model_name(model_name),
            eos=eos,
            max_length=max_length,
            base_url=cfg.get("base_url", "http://localhost:4000/v1"),
            api_key=cfg.get("api_key", ""),
        )
    return StarCoder(model_name, device, eos, max_length)


torch.cuda.empty_cache()
os.environ["TOKENIZERS_PARALLELISM"] = "false"  # disable warning
EOF_STRINGS = ["<|endoftext|>", "###"]


class EndOfFunctionCriteria(StoppingCriteria):
    def __init__(self, start_length, eos, tokenizer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_length = start_length
        self.eos = eos
        self.tokenizer = tokenizer
        self.end_length = {}

    def __call__(self, input_ids, scores, **kwargs):
        """Returns true if all generated sequences contain any of the end-of-function strings."""
        decoded_generations = self.tokenizer.batch_decode(
            input_ids[:, self.start_length :]
        )
        done = []
        for index, decoded_generation in enumerate(decoded_generations):
            finished = any(
                [stop_string in decoded_generation for stop_string in self.eos]
            )
            if (
                finished and index not in self.end_length
            ):  # ensures first time we see it
                for stop_string in self.eos:
                    if stop_string in decoded_generation:
                        self.end_length[index] = len(
                            input_ids[
                                index,  # get length of actual generation
                                self.start_length : -len(
                                    self.tokenizer.encode(
                                        stop_string,
                                        add_special_tokens=False,
                                        return_tensors="pt",
                                    )[0]
                                ),
                            ]
                        )
            done.append(finished)
        return all(done)


class OpenAIChatModel:
    """OpenAI-compatible chat backend (LiteLLM / vLLM / local gateway).

    Exposes the same `generate(prompt, batch_size, temperature, max_length)`
    contract as `StarCoder` so it plugs into Target.generate_model unchanged.
    """

    def __init__(
        self,
        model_name: str,
        eos: List,
        max_length: int,
        base_url: str,
        api_key: str,
    ) -> None:
        from openai import OpenAI

        self.client = OpenAI(base_url=base_url, api_key=api_key or "EMPTY")
        self.model_name = model_name
        self.eos = EOF_STRINGS + (eos or [])
        self.max_length = max_length

    def _one_call(self, prompt: str, temperature: float, max_length: int) -> str:
        from Fuzz4All.util.util import simple_parse

        resp = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=max(temperature, 1e-2),
            max_tokens=max_length,
        )
        content = resp.choices[0].message.content or ""
        code = simple_parse(content)
        return code if code else content

    def generate(
        self, prompt, batch_size=10, temperature=1.0, max_length=512
    ) -> List[str]:
        from concurrent.futures import ThreadPoolExecutor

        outputs: List[str] = [""] * batch_size
        with ThreadPoolExecutor(max_workers=min(batch_size, 8)) as ex:
            futures = {
                ex.submit(self._one_call, prompt, temperature, max_length): i
                for i in range(batch_size)
            }
            for fut in futures:
                i = futures[fut]
                try:
                    outputs[i] = fut.result()
                except Exception as e:
                    outputs[i] = f"// OPENAI_ERROR: {e}"
        return outputs


class StarCoder:
    def __init__(
        self, model_name: str, device: str, eos: List, max_length: int
    ) -> None:
        checkpoint = model_name
        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained(
            checkpoint,
        )
        self.model = (
            AutoModelForCausalLM.from_pretrained(
                checkpoint,
            )
            .to(torch.bfloat16)
            .to(device)
        )
        self.eos = EOF_STRINGS + eos
        self.max_length = max_length
        self.prefix_token = "<fim_prefix>"
        self.suffix_token = "<fim_suffix><fim_middle>"
        self.skip_special_tokens = False

    @torch.inference_mode()
    def generate(
        self, prompt, batch_size=10, temperature=1.0, max_length=512
    ) -> List[str]:
        input_str = self.prefix_token + prompt + self.suffix_token
        input_tokens = self.tokenizer.encode(input_str, return_tensors="pt").to(
            self.device
        )

        scores = StoppingCriteriaList(
            [
                EndOfFunctionCriteria(
                    start_length=len(input_tokens[0]),
                    eos=self.eos,
                    tokenizer=self.tokenizer,
                )
            ]
        )

        raw_outputs = self.model.generate(
            input_tokens,
            max_length=min(self.max_length, len(input_tokens[0]) + max_length),
            do_sample=True,
            top_p=1.0,
            temperature=max(temperature, 1e-2),
            num_return_sequences=batch_size,
            stopping_criteria=scores,
            output_scores=True,
            return_dict_in_generate=True,
            repetition_penalty=1.0,
            pad_token_id=self.tokenizer.eos_token_id,
        )
        gen_seqs = raw_outputs.sequences[:, len(input_tokens[0]) :]
        gen_strs = self.tokenizer.batch_decode(
            gen_seqs, skip_special_tokens=self.skip_special_tokens
        )
        outputs = []
        # removes eos tokens.
        for output in gen_strs:
            min_index = 10000
            for eos in self.eos:
                if eos in output:
                    min_index = min(min_index, output.index(eos))
            outputs.append(output[:min_index])
        return outputs
