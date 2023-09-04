import edge_tts
import asyncio
import yaml
import os
import sys
import argparse

class AutoGen:
    def __init__(self, script_file_path, project_path):
        self.rate = '-4%'
        self.volume = '+0%' 
        self.cook_book = {}
        self.script_file_path = script_file_path
        self.project_path = project_path
    
    def read_script_yaml(self, yaml_file_path):
        try:
            with open(yaml_file_path, 'r', encoding='utf-8') as yaml_file:
                content = yaml.safe_load(yaml_file)
                return content
        except FileNotFoundError:
            print(f"File '.yaml' not found")
        except yaml.YAMLError as e:
            print(f"Error parsing: {e}")

    def create_scene_object(self, solid_scene_name, solid_scene_file_name, clip_duration, keep_full_audio, audio_volume, random_scene_tag, random_scene_duration, is_random):
        scene = {}
        scene["固定镜头名称"] = solid_scene_name
        scene["固定镜头文件名称"] = solid_scene_file_name
        scene["固定镜头片段"] = clip_duration
        scene["固定音频音量"] = audio_volume
        scene["保留全部音频"] = keep_full_audio
        scene["随机镜头类别"] = random_scene_tag
        scene["随机镜头时长"] = random_scene_duration
        scene["是否随机"] = is_random
        return scene

    def create_movie_object(self, title, cover, movie_id, scene_duration, bgm_name, bgm_volume, audio_volume):
        movie = {}
        movie["标题"] = title
        movie["影片封面"] = cover
        movie["编号"] = movie_id
        content = []
        for key,value in scene_duration.items():
            scene = self.create_scene_object("", "", "", False, 0, key, value, True)
            content.append(scene)
        movie["内容顺序"] = content
        bgm = {}
        bgm["文件"] = bgm_name
        bgm["音量"] = bgm_volume
        movie["BGM"] = bgm
        srt = {}
        srt["文件"] = movie_id+".srt"
        srt["字体"] = "yishu.ttf"
        srt["字号"] = 80
        srt["颜色"] = "white"
        movie["字幕"] = srt
        audio = {}
        audio["文件"] = movie_id+".wav"
        audio["音量"] = audio_volume
        movie["音频"] = audio
        tail = {}
        tail["文件"] = "片尾.mp4"
        tail["音量"] = 1
        movie["片尾"] = tail
        return movie

    async def tts(self):
        scene_duration = {}
        #读取脚本文件
        script_config = self.read_script_yaml(self.script_file_path)
        subtitle_list = script_config["脚本"]
        mid = script_config["编号"]
        title = script_config["标题"]
        voice = script_config["配音"]
        mid_path = os.path.join(self.project_path, mid)
        if not os.path.exists(mid_path):
            os.makedirs(mid_path)
        output_file = os.path.join(mid_path ,mid+".wav")
        webvtt_file = os.path.join(mid_path ,mid+".vtt")
        full_text = ""
        #打印数组subtitle_list的长度
        print(f'len(subtitle_list): {len(subtitle_list)}')
        for subtitle in subtitle_list:
            subtitle_text = subtitle["内容"]
            full_text = full_text + subtitle_text + "\n"
        print(full_text)

        #获取倒数第一个item的内容
        last_scene = subtitle_list[-1]["镜头"]

        tts = edge_tts.Communicate(text=full_text, voice=voice, rate=self.rate, volume=self.volume)
        submaker = edge_tts.SubMaker()  
        xt = ""
        du = 0
        i = 0
        with open(output_file, "wb") as file:  
            async for chunk in tts.stream():  
                if chunk["type"] == "audio":  
                    file.write(chunk["data"])  
                elif chunk["type"] == "WordBoundary":  
                    if xt == subtitle_list[i]["内容"] :
                        i = i + 1
                        xt = chunk["text"]
                        du = 0
                    else :
                        xt = xt + chunk["text"]
                        du = du + chunk["duration"]
                    # print(xt)
                    # print(du)
                    #将du转换为秒
                    if subtitle_list[i]["镜头"] == last_scene:
                        scene_duration[subtitle_list[i]["镜头"]] = round(du * 1e-7, 2) + 3
                    else:
                        scene_duration[subtitle_list[i]["镜头"]] = round(du * 1e-7,2) + 1
                    submaker.create_sub((chunk["offset"], chunk["duration"]), chunk["text"]) 
        print(scene_duration)
        srtlines = ""
        with open(webvtt_file, "w", encoding="utf-8") as file:  
            subs = submaker.generate_subs()
            file.write(subs)
            srtlines = vtt_to_srt(subs)
        with open(os.path.join(mid_path, mid+".srt"), "w", encoding="utf-8") as f:
            f.write(srtlines)
        #load yaml
        if os.path.exists(os.path.join(self.project_path, mid, "cookbook.yaml")):
            self.cook_book = self.read_script_yaml(os.path.join(self.project_path, mid, "cookbook.yaml"))
        else:
            cook_book = {}
            cook_book["素材文件前缀"] = "森咖啡"
            cook_book["影片"] = []
            self.cook_book = cook_book
    
        movie = self.create_movie_object(title, "", mid, scene_duration, "Different.mp3", 0.5, 0.8)
        self.cook_book["影片"].append(movie)
        print(len(self.cook_book["影片"]))
        #对象转yaml
        yaml_str = yaml.dump(self.cook_book, allow_unicode=True)
        #写入yaml文件
        with open(os.path.join(self.project_path, mid, "cookbook.yaml"), "w", encoding="utf-8") as f:
            f.write(yaml_str)
    
def vtt_to_srt(vtt_content):    
    lines = vtt_content.strip().split('\n')
    srt_lines = []
    i = 1
    while i < len(lines):
        if '-->' in lines[i]:  # Check for the timestamp line
            vtt_time_range = lines[i].strip()
            vtt_text = lines[i+1].strip().replace(' ', '')
            srt_time_range = vtt_time_range.replace('.', ',')
            srt_line = f"{i//2}\n{srt_time_range}\n{vtt_text}\n"
            srt_lines.append(srt_line)
            i += 2  # Skip the next line
        else:
            i += 1

    return '\n'.join(srt_lines)

if __name__ == "__main__":
    base_path = os.path.dirname(os.path.abspath(__file__))
    # script_base_path = os.path.join(base_path, "脚本")
    # project_base_path = os.path.join(base_path, "工程")

    parse = argparse.ArgumentParser()
    parse.add_argument('-s', "--script", help="provide the script folder")
    parse.add_argument('-p', "--project", help="provide the project folder")
    args = parse.parse_args()
    
    if not args.script:
        print("Please provide the script folder")
        sys.exit(1)
    if not args.project:
        print("Please provide the project folder")
        sys.exit(1)
    
    script_file_path = args.script
    project_path = args.project
    gen = AutoGen(script_file_path, project_path)
    asyncio.run(gen.tts())


    # mid = os.path.basename(sys.argv[0]).split(".")[0]
    # #遍历script_path所有文件
    # for root, dirs, files in os.walk(script_base_path):
    #     for file in files:
    #         if os.path.splitext(file)[1] == '.yaml':
    #             # project_name = os.path.splitext(file)[0].split("-")[0]
    #             # print(project_name)
    #             # project_path = os.path.join(project_base_path, project_name)
    #             script_file_path = os.path.join(root, file)
    #             gen = AutoGen(script_file_path)
    #             asyncio.run(gen.tts())
   
    
