MODELS = {
    "cl": {
        "name_full": "anthropic/claude-opus-4.8",
        "url": "https://openrouter.ai/anthropic/claude-opus-4.8",
        "price": {
            "inp": 5.0,
            "out": 25.0
        }
    },
    
    "cl-f": {
        "name_full": "anthropic/claude-sonnet-4.6",
        "url": "https://openrouter.ai/anthropic/claude-sonnet-4.6",
        "price": {
            "inp": 3.0,
            "out": 15.0
        }
    },
    
    "cl-p": {
        "name_full": "anthropic/claude-fable-5",
        "url": "https://openrouter.ai/anthropic/claude-fable-5",
        "price": {
            "inp": 10.0,
            "out": 50.0
        }
    },
    
    "de": {
        "name_full": "deepseek/deepseek-v4-pro",
        "url": "https://openrouter.ai/deepseek/deepseek-v4-pro",
        "price": {
            "inp": 0.43,
            "out": 0.87
        }
    },
    
    "de-f": {
        "name_full": "deepseek/deepseek-v4-flash",
        "url": "https://openrouter.ai/deepseek/deepseek-v4-flash/pricing",
        "price": {
            "inp": 0.09,
            "out": 0.18
        }
    },
    
    "gp": {
        "name_full": "openai/gpt-5.5",
        "url": "https://openrouter.ai/openai/gpt-5.5",
        "price": {
            "inp": 5.0,
            "out": 30.0
        }
    },
    
    "gp-i": {
        "name_full": "openai/gpt-5.4-image-2",
        "url": "https://openrouter.ai/openai/gpt-5.4-image-2",
        "kind": "image",
        "price": {
            "inp": 8.0,
            "out": 15.0
        }
    },
    
    "gp-p": {
        "name_full": "openai/gpt-5.5-pro",
        "url": "https://openrouter.ai/openai/gpt-5.5-pro",
        "price": {
            "inp": 30.0,
            "out": 180.0
        }
    },
    
    "ge": {
        "name_full": "google/gemini-3.1-pro-preview",
        "url": "https://openrouter.ai/google/gemini-3.1-pro-preview",
        "price": {
            "inp": 2.0,
            "out": 12.0
        }
    },
    
    "ge-f": {
        "name_full": "google/gemini-3.1-flash-lite-preview",
        "url": "https://openrouter.ai/google/gemini-3.1-flash-lite-preview",
        "price": {
            "inp": 0.25,
            "out": 1.5
        }
    },
    
    "ge-i": {
        "name_full": "google/gemini-3-pro-image-preview",
        "url": "https://openrouter.ai/google/gemini-3-pro-image-preview",
        "kind": "image",
        "price": {
            "inp": 2.0,
            "out": 12.0
        }
    },
    
    "gr": {
        "name_full": "x-ai/grok-4.20",
        "url": "https://openrouter.ai/x-ai/grok-4.20",
        "price": {
            "inp": 1.25,
            "out": 2.5
        }
    }
}


def update():
    import copy
    import json
    import os
    import re
    import requests
    
    fpath = os.path.abspath(__file__)

    with open(fpath, 'r') as f:
        content = f.read()

    response = requests.get('https://openrouter.ai/api/v1/models')
    models_data = response.json()
    
    models_map = {model['id']: model for model in models_data['data']}

    updated_models = copy.deepcopy(MODELS)

    def to_cost(name, kind, p_old, p_new):
        p_new = float(p_new) * 1000000
        p_new = float(f'{p_new:.2f}')
        if p_old != p_new:
            text = f'Cost ({kind}) changed for {name}: '
            text += f'{p_old} -> {p_new}'
            print(text)
        return p_new

    for key, model_info in updated_models.items():
        if not 'price' in updated_models[key]:
            updated_models[key]['price'] = {"inp": 0., "out": 0.}
        name_full = model_info['name_full']
        if name_full in models_map:
            p = models_map[name_full].get('pricing', {})
            if p:
                updated_models[key]['price']['inp'] = to_cost(
                    key, 'inp', model_info['price']['inp'], p['prompt'])
                updated_models[key]['price']['out'] = to_cost(
                    key, 'out', model_info['price']['out'], p['completion'])
            else:
                print(f'Can not find price for {name_full}')
        else:
            raise ValueError(f'Can not find info for {name_full}')
    
    models_str = json.dumps(updated_models, indent=4, ensure_ascii=False)
    models_str = models_str.replace('},', '},\n    ')
    models_str = models_str.replace('}}', '}\n}')

    pattern = r"MODELS = \{.*?\}\n\n\n"
    replacement = f"MODELS = {models_str}\n\n\n"
    
    content_new = re.sub(pattern, replacement, content, flags=re.DOTALL)

    with open(fpath, 'w') as f:
        f.write(content_new)

    print('\n\n+++! Info for models is updated\n\n')

    for key, model_info in updated_models.items():
        name = model_info['name_full']
        p_inp = model_info['price']['inp']
        p_out = model_info['price']['out']

        print(f'---> {key:20s} | {name:40s} : {p_inp:-6.2f} / {p_out:-6.2f}')
    
    print('\n\n')


if __name__ == '__main__':
    update()