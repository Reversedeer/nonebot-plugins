import os
import json
import shutil
import tarfile
import nonebot

from pathlib import Path
from typing import NoReturn
from nonebot.log import logger
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import (
    Bot, Message,
    PokeNotifyEvent,
    HonorNotifyEvent,
    GroupUploadNoticeEvent,
    GroupDecreaseNoticeEvent,
    GroupIncreaseNoticeEvent,
    GroupAdminNoticeEvent,
    LuckyKingNotifyEvent,
    GroupMessageEvent
)

from .utils import utils
from .config import config
from .update import updata

class Eventmonitor:
    @staticmethod
    async def chuo(matcher: Matcher, event: PokeNotifyEvent) -> NoReturn:
        if not (await utils.check_chuo(utils.g_temp, str(event.group_id))):
            await matcher.finish(utils.notAllow)
        # 获取用户id    
        uid: str = event.get_user_id()
        try:
            cd = event.time - utils.chuo_CD_dir[uid]                                          
        except KeyError:
            # 没有记录则cd为cd_time+1
            cd: int = utils.chuo_cd + 1                                                            
        if cd > utils.chuo_cd or event.get_user_id() in nonebot.get_driver().config.superusers:
            utils.chuo_CD_dir.update({uid: event.time})
            rely_msg: str = await config.chuo_send_msg()
            await matcher.finish(message=Message(rely_msg))
    #群荣誉事件
    @staticmethod                                                         
    async def qrongyu(matcher: Matcher, event: HonorNotifyEvent, bot: Bot) -> None:
        if not (await utils.check_honor(utils.g_temp, str(event.group_id))):
            return
        bot_qq = int(bot.self_id)
        rely_msg: str = await config.monitor_rongyu(event.honor_type, event.user_id, bot_qq)
        await matcher.finish(message=Message(rely_msg), at_sender=True)

    #群文件事件
    @staticmethod                                                                    
    async def files(matcher: Matcher, event: GroupUploadNoticeEvent) -> None:
        if not (await utils.check_file(utils.g_temp, str(event.group_id))):
            return
        rely_msg: Message= await config.upload_files(event.user_id)
        await matcher.finish(message=rely_msg, at_sender=True)

    #退群事件
    @staticmethod
    async def del_user(matcher: Matcher, event: GroupDecreaseNoticeEvent) -> None:
        if not (await utils.check_del_user(utils.g_temp, str(event.group_id))):
            return
        rely_msg= await config.del_user_bye(event.time, event.user_id)
        await matcher.finish(message=Message(rely_msg))

    #入群事件
    @staticmethod
    async def add_user(matcher: Matcher, event: GroupIncreaseNoticeEvent, bot: Bot) -> None:
        await utils.config_check()
        if not (await utils.check_add_user(utils.g_temp, str(event.group_id))):
            return
        bot_qq = int(bot.self_id)
        rely_msg = await  config.add_user_wecome(event.time, event.user_id, bot_qq)
        await matcher.finish(message=Message(rely_msg), at_sender=True)

    #管理员变动
    @staticmethod
    async def admin_chance(matcher: Matcher, event: GroupAdminNoticeEvent, bot: Bot) -> None:
        if not (await utils.check_admin(utils.g_temp, str(event.group_id))):
            return
        bot_qq = int(bot.self_id)
        rely_msg: str = await config.admin_changer(event.sub_type, event.user_id, bot_qq)
        await matcher.finish(message=Message(rely_msg), at_sender=True)
        
    #红包运气王
    @staticmethod
    async def hongbao(matcher: Matcher, event: LuckyKingNotifyEvent, bot: Bot) -> None:
        if not (await utils.check_red_package(utils.g_temp, str(event.group_id))):
            return
        bot_qq = int(bot.self_id)
        rely_msg = await config.rad_package_change(event.target_id, bot_qq)
        await matcher.finish(message=Message(rely_msg), at_sender=True)

    @staticmethod
    async def switch(matcher: Matcher, event: GroupMessageEvent) -> None:
        # 获取开关指令的参数，即用户输入的指令内容
        command = str(event.get_message()).strip()
        # 获取群组ID
        gid = str(event.group_id)
        # 判断指令是否包含"开启"或"关闭"关键字
        if "开启" in command or "开始" in command:
            if key := utils.get_command_type(command):
                utils.g_temp[gid][key] = True
                utils.write_group_data(utils.g_temp)
                name = utils.get_function_name(key)
                await matcher.finish(f"{name}功能已开启喵")
        elif "禁止" in command or "关闭" in command:
            if key := utils.get_command_type(command):
                utils.g_temp[gid][key] = False
                utils.write_group_data(utils.g_temp)
                name = utils.get_function_name(key)
                await matcher.finish(f"{name}功能已禁用喵")
    
    @staticmethod
    async def state(matcher: Matcher, event:GroupMessageEvent) -> None:
        gid = str(event.group_id)
        with open(utils.address, "r", encoding="utf-8") as f:
            group_status = json.load(f)
        if gid not in group_status:
            await utils.config_check()
        else:
            await matcher.finish(f"群{gid}的Event配置状态：\n" + "\n".join
            (
                [f"{utils.path[func][0]}: {'开启' if group_status[gid][func] else '关闭'}" 
                 for func in utils.path]
            )
        )
            
    @staticmethod
    async def check_bot(matcher: Matcher):
        try:
            code, error = await eventmonitor.check_update(matcher)
            if error:
                logger.error(f"错误: {error}", "插件检查更新")
                await matcher.send(f"更新插件nonebot-plugin-evenrmonitor时发生错误:\n{error}")
        except Exception as e:
            logger.error("更新插件nonebot-plugin-evenrmonitor时发生错误", "检查更新", e=e)
            await matcher.send(f"更新插件nonebot-plugin-evenrmonitor时发生错误 \n{type(e)}: {e}")
        else:
            if code == 200:
                await matcher.finish("更新完毕,请重启bot....")



    @staticmethod
    async def check_update(matcher: Matcher):
        global latest_version
        logger.info("开始检查插件更新...")
        data = await updata.get_latest_version_data()
        if data:
            latest_version = data["name"]
            if utils.current_version < latest_version:
                tar_gz_url = data["tarball_url"]
                logger.info(f"检测到插件nonebot-plugin-evenrmonitor有更新:\n"
                            f"当前版本：{utils.current_version}\n"
                            f"最新版本：{latest_version}")
                await matcher.send(f"检测到插件nonebot-plugin-evenrmonitor有更新:\n"
                                   f"当前版本：{utils.current_version}\n"
                                   f"最新版本：{latest_version}\n"
                                   "开始更新...")
                tar_gz_url = (await updata.fetch_data(tar_gz_url)).headers.get("Location")
                if await updata.download_file(tar_gz_url, updata.latest_tar_gz):
                    logger.info("下载插件最新版文件完成...")
                    error = await eventmonitor._file_handle(latest_version)
                    if error:
                        return 998, error
                    logger.info("更新完毕，清理文件完成...")
                    await matcher.send(message=Message(
                                f"插件更新完成，版本：{utils.current_version} -> {latest_version}\n"
                                f"插件更新日期：{data['created_at']}\n"
                        ),
                    )
                    return 200, ""
                else:
                    logger.warning(f"下载最新版本失败..请检查网络是否通畅\n"
                                   f"版本号：{latest_version}")
                    await matcher.send(
                        f"下载最新版本失败>_<请检查网络是否通畅\n"
                        f"版本号：{latest_version}")
            elif utils.current_version == latest_version:
                logger.info(f"自动获取版本成功：{latest_version}，当前版本为最新版，无需更新...")
                await matcher.send(f"自动获取版本成功：{latest_version}，当前版本为最新版，无需更新...")
            else:
                logger.warning(f"当前版本{utils.current_version}已大于最新版本，不要随意修改文件喵~")
                await matcher.send(f"当前版本{utils.current_version}已大于最新版本，不要随意修改文件喵~")
        else:
            logger.warning("自动获取版本失败....")
            await matcher.send("自动获取版本失败...")
        return 999, ""

    @staticmethod
    async def _file_handle(latest_version: str) -> str:
        # 接收最新版本号作为参数，并返回处理结果字符串
        
        if not updata.temp_dir.exists():
            # 检查临时目录是否存在，如果不存在则创建
            updata.temp_dir.mkdir(exist_ok=True, parents=True)
        
        if updata.backup_dir.exists():
            # 如果备份目录存在，则删除整个备份目录
            shutil.rmtree(updata.backup_dir)
        tf = None
        # 初始化一个tarfile对象tf
        updata.backup_dir.mkdir(exist_ok=True, parents=True)
        # 创建备份目录，如果备份目录已存在，则不会重新创建
        logger.info("开始解压文件压缩包....")
        # 记录日志，表示开始解压文件压缩包
        tf = tarfile.open(updata.latest_tar_gz)
        # 打开文件压缩包，获取tarfile对象tf
        tf.extractall(updata.temp_dir)
        # 将压缩包中的所有文件解压到临时目录temp_dir中
        logger.info("解压文件压缩包完成....")
        # 记录日志，表示解压文件压缩包完成
        latest_file = Path(updata.temp_dir) / os.listdir(updata.temp_dir)[0]
        # 获取临时目录中的第一个文件，作为最新版本的文件夹路径
        update_info_file = Path(latest_file) / "nonebot_plugin_eventmonitor"
        # 获取最新版本文件夹中的第二个文件，作为更新信息文件的路径
        try:
            pycache_dir = os.path.join(updata.destination_directory, '__pycache__')
            if os.path.exists(pycache_dir):
                shutil.rmtree(pycache_dir)

            logger.info("正在备份插件目录...")
            for file in os.listdir(updata.destination_directory):
                if file != '__pycache__':
                    temp_file = os.path.join(updata.destination_directory, file)
                    backup_file = os.path.join(updata.backup_dir, file)
                    shutil.copy2(temp_file, backup_file)
            logger.info("文件备份成功")
            if os.path.exists(updata.destination_directory):
                shutil.rmtree(updata.destination_directory)            
            logger.info("开始更新插件...")
            for file in os.listdir(update_info_file): 
                
                updata_file = os.path.join(update_info_file, file)
                destination_file = os.path.join(updata.destination_directory, file)
                shutil.copy2(updata_file, destination_file)
            logger.info("插件更新成功!")
        except Exception as e:
            raise e
        if tf:
            tf.close()
            # 关闭tarfile对象，释放资源
        if updata.temp_dir.exists():
            shutil.rmtree(updata.temp_dir)
            # 删除临时目录及其中的所有文件
        if updata.latest_tar_gz.exists():
            updata.latest_tar_gz.unlink()
            # 删除最新版本的压缩包文件
        with open(updata.version_file, "w", encoding="utf-8") as f:
            f.write(f"{latest_version}")
            # 将最新版本号写入版本文件中
        os.system(f"poetry run pip install -r {(update_info_file / 'pyproject.toml').absolute()}")
        # 使用os.system命令执行shell命令，安装更新后的依赖包
        return ""
        # 返回一个空字符串

eventmonitor = Eventmonitor()