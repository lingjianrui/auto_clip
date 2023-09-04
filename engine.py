from moviepy.editor import VideoFileClip, concatenate_videoclips, CompositeVideoClip, ImageClip, afx, AudioFileClip, CompositeAudioClip, TextClip
from moviepy.video.tools.drawing import color_gradient
from moviepy.video.tools.subtitles import SubtitlesClip
from PIL import Image, ImageDraw, ImageFont
from concurrent.futures import ThreadPoolExecutor
import threading
import random
import yaml
import sys
import os
import argparse

class Engine:
    """
    这个类用于自动混剪视频
    """
    def __init__(self, prefix, video_title, project_path, assets_path, movie_cover, bgm_obj, audio_obj, subtitle_obj, tail_obj, mid):
        self.prefix = prefix
        self.video_title = video_title
        self.project_path = project_path
        self.assets_path = assets_path
        self.movie_cover = movie_cover
        self.bgm_obj = bgm_obj
        self.audio_obj = audio_obj
        self.subtitle_obj = subtitle_obj
        self.tail_obj = tail_obj
        self.clips_path_map = {}
        self.clips_path_lock = threading.Lock()
        self.mid = mid

    def process_video_content(self, content):
        """
        功能: 处理视频内容
        参数:
            content: 配置文件中的内容顺序对象
        返回值: 无
        """
        print("开始处理视频内容")
        new_video_name = self.mid
        with ThreadPoolExecutor(max_workers=5) as executor:  # Adjust max_workers as needed
            futures = []
            clips_keys = []
            for item in content:
                if item["是否随机"]: 
                    tag = item["随机镜头类别"]
                    scene_time = item["随机镜头时长"]
                    keep_full_audio = item["保留全部音频"]
                    audio_volume = 0
                    selectedFileName = random_file_in_subfolder(os.path.join(self.assets_path, tag), prefix)
                    selectedFilePath = os.path.join(self.assets_path, tag, selectedFileName)
                    print("selectedFilePath:", selectedFilePath)
                    info = self.get_video_info(selectedFilePath)
                    duration = round(info["duration"],2)
                    scene_time = round(scene_time,2)
                    print(f"duration: {duration}")
                    print(f"scene_time: {scene_time}")
                    if duration <= scene_time:
                        start_time = 0
                        end_time = start_time + duration
                    else:
                        start_time = random_number(0, duration - scene_time)
                        end_time = start_time + scene_time

                    #创建线程
                    future = executor.submit(self.clip_video, tag, selectedFilePath, start_time, end_time, new_video_name,  keep_full_audio, audio_volume)
                    futures.append(future)
                    clips_keys.append(tag)
                else: 
                    clip_name = item["固定镜头名称"]
                    clip_file = os.path.join(self.project_path, item["固定镜头文件名称"])
                    clip_snippet = item["固定镜头片段"].split("-")
                    clip_snippet_start = clip_snippet[0]
                    clip_snippet_end = clip_snippet[1]
                    keep_full_audio = item["保留全部音频"]
                    audio_volume = item["固定音频音量"]
                    #创建线程
                    future = executor.submit(self.clip_video, clip_name, clip_file, clip_snippet_start, clip_snippet_end, new_video_name, keep_full_audio, audio_volume)
                    futures.append(future)
                    clips_keys.append(clip_name)


            #等待所有线程完成
            for future in futures:
                future.result()
            print("=========================")
            print(self.video_title)
            print(clips_keys)
            print(self.clips_path_map)
            print("=========================")
            #获取片尾文件路径
            output_path = os.path.join(".", self.project_path, new_video_name + ".mp4")
            self.merge_videos(self.clips_path_map, clips_keys, output_path, self.video_title, self.bgm_obj, self.audio_obj, self.subtitle_obj, self.tail_obj)

    
    def clip_video(self, tag, video_path, start_time, end_time, new_video_name, keep_full_audio, audio_volume):
        """
        功能: 多线程剪切视频
        参数:
            tag: 素材类别
            video_path: 视频文件路径
            start_time: 开始时间
            end_time: 结束时间
            new_video_name: 新视频名称
        返回值: 无
        """
        try:
            #根据video_path获取文件名
            file_name = os.path.basename(video_path)
            video_clip = VideoFileClip(video_path)
            #如果确定了这个镜头需要保留完整的音频, 就存在工程目录中
            if keep_full_audio:
                audio = video_clip.audio.volumex(audio_volume)
                audio.write_audiofile(video_path+"-audio.mp3")
                audio_clip_path = video_path+"-audio.mp3"
            else:
                video_clip_audio = video_clip.audio.volumex(audio_volume)
                audio_clip_path = None
                video_clip = video_clip.set_audio(video_clip_audio)
            video_clip = video_clip.subclip(start_time, end_time)
            #新视频片段文件夹
            clips_path = self.project_path
            #创建文件夹
            new_clip_path = os.path.join(clips_path, file_name)

            with self.clips_path_lock:
                self.clips_path_map[tag] = {"new_clip_path": new_clip_path, "keep_full_audio": keep_full_audio, "audio_clip": audio_clip_path}
                #将所有的视频片段全路径保存到一个数组中
                video_clip.write_videofile(os.path.join(clips_path, file_name), codec="libx264", preset="ultrafast")
                video_clip.close()

        except Exception as e:
            print(f"Error: {e}")

    
    def merge_videos(self, video_clips_map, clips_keys, output_path, video_title, bgm_obj, audio_obj, subtitle_obj, tail_obj):
        """
        功能: 多线程合并视频
        参数:
            video_clips_map: 视频片段字典
            clips_keys: 视频片段字典的key数组
            output_path: 输出路径
            tail_clip_path: 片尾文件路径
        返回值: 无
        """
        video_clips = []
        audio_clips = []
        audio_clips_file = []
        final_time = 0
        #增加封面 使用第一个片段的第一针作为视频封面
        print(f"clips_keys : {clips_keys[0]} ")
        first_clip_meta = video_clips_map[clips_keys[0]]
        first_clip_path = first_clip_meta["new_clip_path"]
        print(f"first_clip_path : {first_clip_path} ")
        first_clip_keep_full_audio = first_clip_meta["keep_full_audio"]
        first_clip = VideoFileClip(first_clip_path)
        if first_clip_keep_full_audio: 
            first_audio_clip = first_clip_meta["audio_clip"]
            audio_clips_file.append(first_audio_clip)
        first_frame = first_clip.reader.get_frame(0)
        frame_image = Image.fromarray(first_frame)
        frame_image.save(output_path+".png")
        #加水印保存成封面
        self.add_watermark(output_path+".png", video_title, output_path+".png")
        #读取封面图片
        cover_image = ImageClip(output_path+".png")
        cover_image = cover_image.set_duration(0.1)
        cover_image = cover_image.set_position(("center","center"))
        #将封面和第一个片段合并
        watermarked_clip = CompositeVideoClip([first_clip, cover_image])
        #添加到待合成数组中
        video_clips.append(watermarked_clip)
        first_clip.reader.close()

        final_time = final_time + watermarked_clip.duration
        #从第二个片段开始，将所有片段合并到一个数组中
        for key in clips_keys[1:]: 
            clip_meta = video_clips_map[key]
            clip_path = clip_meta["new_clip_path"]
            clip_keep_full_audio = clip_meta["keep_full_audio"]
            if not os.path.exists(clip_path):
                continue
            video_clip = VideoFileClip(clip_path)
            if clip_keep_full_audio:
                audio_clip = clip_meta["audio_clip"]
                audio_clips_file.append(audio_clip)
            new_clip = video_clip.fadein(0.3).fadeout(0.3)
            final_time = final_time + new_clip.duration
            video_clips.append(new_clip)
        
        #背景音乐
        if bgm_obj:
            bgm_file = os.path.join(self.assets_path, "BGM", bgm_obj["文件"])
            bgm_vol = bgm_obj["音量"]
            bgm_clip = AudioFileClip(bgm_file).volumex(bgm_vol)
            bgm_audio_track = afx.audio_loop(bgm_clip, duration=final_time)
            audio_clips.append(bgm_audio_track)

        #音频
        if audio_obj:
            #音频文件
            audio_file = os.path.join(self.project_path, audio_obj["文件"])
            #音频文件音量
            audio_file_vol = audio_obj["音量"]
            main_track = AudioFileClip(audio_file).volumex(audio_file_vol)
            audio_clips.append(main_track)
        
        #片尾
        if tail_obj:
            tail_clip = VideoFileClip(os.path.join(self.assets_path, "片尾", tail_obj["文件"]))
            tail_audio_track = tail_clip.audio.volumex(tail_obj["音量"])
            tail_clip = tail_clip.set_audio(tail_audio_track)
            tail_clip = tail_clip.set_duration(tail_clip.duration)
            video_clips.append(tail_clip)

        #遍历所有clip中的full音频文件
        for file_path in audio_clips_file:
            audio_clip = AudioFileClip(file_path)
            audio_clips.append(audio_clip)

        if video_clips:
            final_clip = concatenate_videoclips(video_clips)
            video_audio_clip = final_clip.audio.volumex(1)
            audio_clips.append(video_audio_clip)
            #视频声音和背景音乐，音频叠加
            audio_clip_add = CompositeAudioClip(audio_clips)

            if subtitle_obj:
                #字幕文件
                subtitle_file = os.path.join(self.project_path, subtitle_obj["文件"])
                #视频写入字幕
                final_video = self.add_subtitle(subtitle_file, final_clip, subtitle_obj["字体"], subtitle_obj["字号"], subtitle_obj["颜色"])
            else: 
                final_video = final_clip

            #视频写入背景音乐 
            final_video = final_video.set_audio(audio_clip_add)
            final_video.write_videofile(output_path, codec='libx264')
            
            # final_clip.write_videofile(output_path, codec='libx264')
            final_video.close()
        
    def add_watermark(self, image_path, watermark_text, output_path):
        """
        功能: 生成标题
        参数:
            image_path: 图片路径
            watermark_text: 水印文本
            output_path: 输出路径
        返回值: 无
        """
        image = Image.open(image_path).convert("RGBA")
    
        # 创建一个新图像用于文本图层
        text_layer = Image.new("RGBA", image.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(text_layer)
        
        # 设置字体和大小
        font = ImageFont.truetype("yishu.ttf", 130)  # 使用你的字体文件和字体大小
        
        # 在文本图层上绘制文本
        if watermark_text.find("#") != -1:
            texts = watermark_text.split("#")
        else:
            texts = [watermark_text]

        for index, text in enumerate(texts):
            
            # 获取文本的宽度和高度
            text_width, text_height = draw.textsize(text, font=font)
            
            if len(texts) == 1:
                # 计算文本放置的位置（底部中心）
                x = (image.width - text_width) // 2
                y = image.height // 2 - text_height + 70
            else:
                # 计算文本放置的位置（底部中心）
                x = (image.width - text_width) // 2
                y = image.height // 2 - text_height + index * 150
            draw.text((x, y), text, font=font, fill='white')
        
        x1, y1, x2, y2 = 0, 750, image.width, 1200
        region = image.crop((x1, y1, x2, y2))
        region = adjust_brightness(region, -50)
        image.paste(region, (x1, y1))
        
        # 合并文本图层和原图像
        watermarked_image = Image.alpha_composite(image, text_layer)
        watermarked_image.show()
        # 保存带有文本水印的图像
        watermarked_image.save(output_path, format="PNG")

    def add_subtitle(self, subtitle_file, final_clip, font_name, font_size, font_color):

        generator = lambda txt: TextClip(txt, font=font_name, fontsize=font_size, color=font_color, kerning=-2, interline=-1, size=(1000,500), method='caption')
        # generator = lambda txt: TextClip(txt, font=font_name, fontsize=font_size, color=font_color)

        subs = SubtitlesClip(subtitle_file, generator)
        subs = subs.set_duration(final_clip.duration)
        print(f'subs.duration: {subs.duration}')
        final_video = CompositeVideoClip([final_clip, subs.set_pos(('center','center'))],use_bgclip=True)
        return final_video
    
    def get_video_info(self, video_path):
        """
        功能: 获取视频文件时长
        参数:
            video_path: 视频文件路径
        返回值: info对象
        """
        try:
            info = {}
            clip = VideoFileClip(video_path)
            duration = clip.duration
            clip.close()
            info["duration"] = duration
            return info
        except Exception as e:
            print(f"Error: {e}")
            return None
        

def read_cookbook_yaml(folder_path):
    """
    功能: 构建 cookbook.yaml 文件对象
    参数:
        folder_path: yaml配置文件路径
    返回值: yaml配置文件对象
    """
    yaml_path = os.path.join(folder_path, 'cookbook.yaml')
    try:
        with open(yaml_path, 'r', encoding='utf-8') as yaml_file:
            content = yaml.safe_load(yaml_file)
            return content
    except FileNotFoundError:
        print(f"File 'cookbook.yaml' not found in {folder_path}")
    except yaml.YAMLError as e:
        print(f"Error parsing 'cookbook.yaml': {e}")


def random_file_in_subfolder(folder_path, prefix):
    """
    功能: 随机读取这个文件夹的子文件夹中的文件名称
    参数:
        folder_path: tag文件夹路径
        prefix: 素材视频文件前缀
    返回值: 在tag文件夹中随机选择一个子文件夹 在子文件夹中随机选择一个文件路径返回
    """
    # 获取文件夹下的子文件夹列表
    subfolders = [subfolder for subfolder in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, subfolder))]
    
    if not subfolders:
        print("No subfolders found in the provided folder.")
        return
    # 随机选择一个子文件夹
    selected_subfolder = random.choice(subfolders)
    
    # 获取选定子文件夹中的文件列表
    subfolder_path = os.path.join(folder_path, selected_subfolder)
    files_in_subfolder = [file for file in os.listdir(subfolder_path) if os.path.isfile(os.path.join(subfolder_path, file)) and file.startswith(prefix)]
    
    if not files_in_subfolder:
        print(f"No files found in the selected subfolder '{selected_subfolder}'.")
        return
    
    # 随机选择一个文件名称
    selected_file = random.choice(files_in_subfolder)
    return os.path.join(selected_subfolder,selected_file)

def random_str(randomlength=8):
    """
    功能: 随机字符串
    参数:
        randomlength: 默认是8位
    返回值: 返回n位随机字符串
    """
    str = ''
    chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    length = len(chars) - 1
    for i in range(randomlength):
        str += chars[random.randint(0, length)]
    return str

def random_number(min, max):
    """
    功能: 范围随机数字
    参数:
        min: 最小值
        max: 最大值
    返回值: 在min-max范围内的随机数
    """
    print(f"min: {min}, max: {max}")
    min = round(min, 2)
    max = round(max, 2)
    return random.randint(min*100, max*100) / 100

def adjust_brightness(image, brightness):
    """
    功能: 调整图片亮度
    参数: 
        image: 要调整的图片
        brightness: 亮度值,取值范围为[-100, 100],0表示原始亮度
    返回值: 亮度调整后的图片
    """

    # 获取图片的RGB像素信息
    pixels = image.load()
    width, height = image.size

    # 计算像素值的调整量
    adjust = 1 + brightness / 100.0
    
    # 遍历所有像素点，进行亮度调整
    for x in range(width):
        for y in range(height):
            r, g, b, t = pixels[x, y]
            pixels[x, y] = (
                int(r * adjust),
                int(g * adjust),
                int(b * adjust),
                int(t)
            )
    return image

def NewInstance(prefix, video_title, project_path, assets_path, video_content, movie_cover, bgm_obj, audio_obj, subtitle_obj, tail_obj, mid): 
    """
    功能: 一个Engine的执行单元(实例)
    参数: 
        prefix: 素材视频文件前缀
        video_title: 视频标题
        assets_path: 素材文件夹路径
    返回值: 无
    """
    gen = Engine(prefix, video_title, project_path, assets_path, movie_cover, bgm_obj, audio_obj, subtitle_obj, tail_obj, mid)
    gen.process_video_content(video_content)

if __name__ == "__main__":
    # assets_path = "素材"
    # project_path = "工程"

    parse = argparse.ArgumentParser()
    parse.add_argument('-p', "--project", nargs='+', type=str, help="provide the project folder")
    parse.add_argument('-a', "--assets", help="provide the assets folder")
    args = parse.parse_args()

    if not args.project:
        print("project folder not set")
        sys.exit(1)
    if not args.assets:
        print("assets folder not set")
        sys.exit(1)

    project_path_list = args.project
    assets_path = args.assets

    # project_name = os.path.basename(project_path)
    # print("project_name:", project_name)
    with ThreadPoolExecutor(max_workers=5) as executor:  # Adjust max_workers as needed
        futures = []
        for project_path in project_path_list:
            content = read_cookbook_yaml(project_path)
            if content:
                movies = content["影片"]
                
                # count = len(video_title_array)
                prefix = content["素材文件前缀"]
                # video_tail = content["片尾"]
                print("初始化prefix:", prefix)
                m = movies[0]
                for m in movies:
                    video_title = m["标题"]
                    print("video_title:", video_title)
                    video_content = m["内容顺序"]
                    movie_cover = m["影片封面"]
                    bgm_obj = m["BGM"]
                    subtitle_obj = m["字幕"]
                    audio_obj = m["音频"]
                    tail_obj = m["片尾"]
                    mid = m["编号"]
                    future = executor.submit(NewInstance, prefix, video_title, project_path, assets_path, video_content, movie_cover, bgm_obj, audio_obj, subtitle_obj, tail_obj, mid)
                    futures.append(future)

        # Wait for all threads to complete
        for future in futures:
            future.result()    
            print("视频合成完成")

            

