from transformers import MllamaForConditionalGeneration, AutoProcessor, TextIteratorStreamer
from PIL import Image
import requests
import torch
from threading import Thread
import gradio as gr
from gradio import FileData
import time
import spaces

# 需要修改模型路径
ckpt = "/home/rickychen/桌面/llm/models/test1"
model = MllamaForConditionalGeneration.from_pretrained(ckpt,
    torch_dtype=torch.bfloat16).to("cuda")
processor = AutoProcessor.from_pretrained(ckpt)


@spaces.GPU
def bot_streaming(message, history, max_new_tokens=250):
    
    txt = message["text"]
    ext_buffer = f"{txt}"
    
    messages= [] 
    images = []
    

    for i, msg in enumerate(history): 
        if isinstance(msg[0], tuple):
            messages.append({"role": "user", "content": [{"type": "text", "text": history[i+1][0]}, {"type": "image"}]})
            messages.append({"role": "assistant", "content": [{"type": "text", "text": history[i+1][1]}]})
            images.append(Image.open(msg[0][0]).convert("RGB"))
        elif isinstance(history[i-1], tuple) and isinstance(msg[0], str):
            # messages are already handled
            pass
        elif isinstance(history[i-1][0], str) and isinstance(msg[0], str): # text only turn
            messages.append({"role": "user", "content": [{"type": "text", "text": msg[0]}]})
            messages.append({"role": "assistant", "content": [{"type": "text", "text": msg[1]}]})

    # add current message
    if len(message["files"]) == 1:
        
        if isinstance(message["files"][0], str): # examples
            image = Image.open(message["files"][0]).convert("RGB")
        else: # regular input
            image = Image.open(message["files"][0]["path"]).convert("RGB")
        images.append(image)
        messages.append({"role": "user", "content": [{"type": "text", "text": txt}, {"type": "image"}]})
    else:
        messages.append({"role": "user", "content": [{"type": "text", "text": txt}]})


    texts = processor.apply_chat_template(messages, add_generation_prompt=True)

    if images == []:
        inputs = processor(text=texts, return_tensors="pt").to("cuda")
    else:
        inputs = processor(text=texts, images=images, return_tensors="pt").to("cuda")
    streamer = TextIteratorStreamer(processor, skip_special_tokens=True, skip_prompt=True)

    generation_kwargs = dict(inputs, streamer=streamer, max_new_tokens=max_new_tokens)
    generated_text = ""
    
    thread = Thread(target=model.generate, kwargs=generation_kwargs)
    thread.start()
    buffer = ""
    
    for new_text in streamer:
        buffer += new_text
        generated_text_without_prompt = buffer
        time.sleep(0.01)
        yield buffer


demo = gr.ChatInterface(fn=bot_streaming, title="Multimodal Llama", examples=[
    [{"text": "Which era does this piece belong to? Give details about the era.", "files":["./examples/rococo.jpg"]},
    200],
    [{"text": "Where do the droughts happen according to this diagram?", "files":["./examples/weather_events.png"]},
    250],
    [{"text": "What happens when you take out white cat from this chain?", "files":["./examples/ai2d_test.jpg"]},
    250],
    [{"text": "How long does it take from invoice date to due date? Be short and concise.", "files":["./examples/invoice.png"]},
    250],
    [{"text": "Where to find this monument? Can you give me other recommendations around the area?", "files":["./examples/wat_arun.jpg"]}, 
    250],
    ],
      textbox=gr.MultimodalTextbox(), 
      additional_inputs = [gr.Slider(
              minimum=10,
              maximum=500,
              value=250,
              step=10,
              label="Maximum number of new tokens to generate",
          )
        ],
      cache_examples=False,
      description="Try Multimodal Llama by Meta with transformers in this demo. Upload an image, and start chatting about it, or simply try one of the examples below. To learn more about Llama Vision, visit [our blog post](https://huggingface.co/blog/llama32). ",
      stop_btn="Stop Generation", 
      fill_height=True,
    multimodal=True)
    
demo.launch(debug=True, server_name="0.0.0.0")
