import discord
import env

import textwrap
import random
import datetime

import os
import psycopg2
from psycopg2.extras import DictCursor

def key_parser(message, keyword_list):
    has_keyword = False
    for key in keyword_list:
        if key in message.content:
            has_keyword = True
            break
    return has_keyword

class GameRPS:
    __rps_done_member_list = []
    __msg_daily_limit_exceeded = textwrap.dedent("""\
        じゃんけんは1日1回まで！
        ほな、また明日！
    """)
    __msg_too_many_hands = textwrap.dedent("""\
        手を複数同時に出すのは反則やで！
    """)
    __msg_win = textwrap.dedent("""\
        やるやん。
        明日は俺にリベンジさせて。
        では、どうぞ。
    """)
    __msg_lose_r = textwrap.dedent("""\
        俺の勝ち！
        負けは次につながるチャンスです！
        ネバーギブアップ！
        ほな、いただきます！
    """)
    __msg_lose_s = textwrap.dedent("""\
        俺の勝ち！
        たかがじゃんけん、そう思ってないですか？
        それやったら明日も、俺が勝ちますよ
        ほな、いただきます！
    """)
    __msg_lose_p = textwrap.dedent("""\
        俺の勝ち！
        なんで負けたか、明日まで考えといてください。
        そしたら何かが見えてくるはずです
        ほな、いただきます！
    """)
    __filenames_win = [
        "honda_win.png"
    ]
    __filenames_lose_r = [
        # "honda_p.png",
        "honda_p.gif"
    ]
    __filenames_lose_s = [
        # "honda_r.png",
        "honda_r.gif"
    ]
    __filenames_lose_p = [
        # "honda_s.png",
        "honda_s.gif"
    ]

    __youtube_lose_r = "https://youtu.be/LhPJcvJLNEA"
    __youtube_lose_s = "https://youtu.be/SWNCYpeDTfo"
    __youtube_lose_p = "https://youtu.be/28d78XP1TJs"

    def __init__(self):
        pass

    def __get_connection(self):
        dsn = env.DATABASE_URL
        return psycopg2.connect(dsn, sslmode='require')

    def __parse_hands(self, message):
        r = key_parser(message, env.HAND_R_KEYWORDS)
        p = key_parser(message, env.HAND_P_KEYWORDS)
        s = key_parser(message, env.HAND_S_KEYWORDS)
        return [r, p, s]

    def __check_player_rights(self, player):
        with self.__get_connection() as conn:
            conn.autocommit = True
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute('SELECT * FROM honda_bot_users')
                rows = cur.fetchall()
                player_id = player.id
                player_name = player.name
                dt_now, dt_prev_refresh, dt_next_refresh = env.get_dt_now_and_dt_prev_next_refresh()
                for row in rows:
                    if row["id"] == player_id:
                        dt_last_accessed = row["last_accessed"]
                        if dt_last_accessed == None or dt_last_accessed < dt_prev_refresh:
                            return True, None, None
                        else:
                            return False, dt_last_accessed, dt_next_refresh
                cur.execute('INSERT INTO honda_bot_users (id, name, battle_count_total, battle_count_win, battle_count_lose) VALUES (%s, %s, %s, %s, %s)', (player_id, player_name, 0, 0, 0))
                return True, None, None

    def __update_player_access_and_battle_count(self, player, result):
        with self.__get_connection() as conn:
            conn.autocommit = True
            with conn.cursor(cursor_factory=DictCursor) as cur:
                player_id = player.id
                dt_now = datetime.datetime.now()
                cur.execute('UPDATE honda_bot_users SET last_accessed = %s WHERE id = %s', (dt_now, player_id))
                cur.execute('UPDATE honda_bot_users SET battle_count_total = battle_count_total + 1 WHERE id = %s', (player_id,))
                if result == 'W':
                    cur.execute('UPDATE honda_bot_users SET battle_count_win = battle_count_win + 1 WHERE id = %s', (player_id,))
                elif result == 'L':
                    cur.execute('UPDATE honda_bot_users SET battle_count_lose = battle_count_lose + 1 WHERE id = %s', (player_id,))

    async def __play_youtube(self, voice, url):
        player = await voice.create_ytdl_player(url)
        player.start()

    def __create_rps_battle_string(self, player, hands, result='L'): # result: win->'W' lose->'L'
        player_hand = None
        honda_hand = None
        r, p, s = hands
        if result == 'W':
            if r is True:
                player_hand = env.EMOJI_R
                honda_hand = env.EMOJI_S
            elif s is True:
                player_hand = env.EMOJI_S
                honda_hand = env.EMOJI_P
            elif p is True:
                player_hand = env.EMOJI_P
                honda_hand = env.EMOJI_R
        elif result == 'L':
            if r is True:
                player_hand = env.EMOJI_R
                honda_hand = env.EMOJI_P
            elif s is True:
                player_hand = env.EMOJI_S
                honda_hand = env.EMOJI_R
            elif p is True:
                player_hand = env.EMOJI_P
                honda_hand = env.EMOJI_S
        if player_hand is not None and honda_hand is not None:
            return "(YOU) " + player_hand + " VS " + honda_hand + " (HONDA)\n"
        else:
            return ""


    async def __play_rps(self, ch, player, hands, m_prefix=""):
        r, p, s = hands
        rnd = random.random()

        if rnd < env.WIN_RATE:
            battle_result = 'W'
        else:
            battle_result = 'L'

        m_prefix = m_prefix + self.__create_rps_battle_string(player, hands, battle_result)

        if battle_result == 'W':
            f = [discord.File(filename) for filename in self.__filenames_win]
            m = self.__msg_win
        elif battle_result == 'L':
            if r is True:
                f = [discord.File(filename) for filename in self.__filenames_lose_r]
                m = self.__msg_lose_r
            elif s is True:
                f = [discord.File(filename) for filename in self.__filenames_lose_s]
                m = self.__msg_lose_s
            elif p is True:
                f = [discord.File(filename) for filename in self.__filenames_lose_p]
                m = self.__msg_lose_p

        await ch.send(m_prefix + m, files=f)
        self.__update_player_access_and_battle_count(player, battle_result) # update user's last access time when rps is done
        return

    async def process_message(self, client, message):
        player = message.author
        hands = self.__parse_hands(message)
        ch = message.channel

        if hands.count(True) == 0:
            return

        m_prefix = player.mention + "\n"

        # judge rights
        player_rights, dt_last_accessed, dt_prev_refresh = self.__check_player_rights(player)
        if player_rights is False:
            m = self.__msg_daily_limit_exceeded
            await ch.send(m_prefix + m)
            return

        if hands.count(True) > 1:
            m = self.__msg_too_many_hands
            await ch.send(m_prefix + m)
        else:
            assert hands.count(True) == 1, 'assert: [r, p, s].count(True) == 1 ... r:{0}, p:{1}, s:{2}'.format(hands[0], hands[1], hands[2])

            await self.__play_rps(ch, player, hands, m_prefix)


async def respond_greeting(message):
    if message.content.startswith("おはよう"):
        m = "おはようございます" + message.author.name + "さん！"
        await message.channel.send(m)
    if message.content.startswith("こんにちは"):
        m = "ちーっす、" + message.author.name + "さん！"
        await message.channel.send(m)
    if message.content.startswith("こんばんは"):
        m = "こんばんは、" + message.author.name + "さん！"
        await message.channel.send(m)
