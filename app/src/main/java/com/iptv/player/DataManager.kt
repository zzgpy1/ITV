package com.iptv.player

import android.content.Context
import android.util.Log
import com.iptv.player.model.Channel
import com.iptv.player.model.ChannelGroup
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

object DataManager {
    private const val TAG = "DataManager"
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    var allChannels: List<Channel> = emptyList()
    var channelGroups: List<ChannelGroup> = emptyList()

    suspend fun loadChannels(context: Context): Boolean = withContext(Dispatchers.IO) {
        try {
            val m3uUrl = BuildConfig.IPTV_M3U_URL
            Log.i(TAG, "Loading M3U from $m3uUrl")
            val request = Request.Builder().url(m3uUrl).build()
            val response = client.newCall(request).execute()

            if (!response.isSuccessful) {
                Log.e(TAG, "HTTP error: ${response.code}")
                return@withContext false
            }

            val content = response.body?.string() ?: return@withContext false
            val channels = parseM3uContent(content)

            if (channels.isEmpty()) {
                Log.e(TAG, "Parsed 0 channels from M3U")
                return@withContext false
            }

            allChannels = channels
            channelGroups = groupChannels(channels)

            Log.i(TAG, "Loaded ${channels.size} channels, ${channelGroups.size} groups")
            return@withContext true
        } catch (e: Exception) {
            Log.e(TAG, "Error loading channels", e)
            return@withContext false
        }
    }

    private fun parseM3uContent(content: String): List<Channel> {
        val channels = mutableListOf<Channel>()
        val lines = content.lines()
        var i = 0
        var currentGroup = ""

        while (i < lines.size) {
            val line = lines[i].trim()
            when {
                line.startsWith("#EXTINF") -> {
                    // 提取频道名（逗号之后）
                    val nameStart = line.indexOf(',')
                    val name = if (nameStart != -1) line.substring(nameStart + 1).trim() else "未知频道"
                    // 提取 group-title（如果有）
                    val groupMatch = Regex("""group-title="([^"]+)"""").find(line)
                    val group = groupMatch?.groupValues?.get(1) ?: currentGroup
                    // 下一行应该是 URL
                    if (i + 1 < lines.size) {
                        val urlLine = lines[i + 1].trim()
                        if (urlLine.startsWith("http")) {
                            channels.add(Channel(name, urlLine, group))
                        } else {
                            Log.w(TAG, "Skipping non-http URL: $urlLine")
                        }
                    }
                    i += 2
                }
                line.startsWith("#") -> {
                    // 注释行可能是分组信息（如 # 央视）
                    if (line.startsWith("# ") || line.startsWith("#\uD83D\uDCFA") || line.matches(Regex("#[\\u4e00-\\u9fa5]+"))) {
                        currentGroup = line.drop(1).trim()
                    }
                    i++
                }
                line.isBlank() -> i++
                else -> {
                    // 单独 URL 行（无 EXTINF）
                    if (line.startsWith("http")) {
                        channels.add(Channel("频道${channels.size + 1}", line, currentGroup))
                    }
                    i++
                }
            }
        }
        Log.i(TAG, "Parsed ${channels.size} channels from M3U")
        return channels
    }

    private fun groupChannels(channels: List<Channel>): List<ChannelGroup> {
        val groupMap = mutableMapOf<String, MutableList<Channel>>()
        channels.forEach { channel ->
            val groupName = channel.group.ifEmpty { "其他" }
            groupMap.getOrPut(groupName) { mutableListOf() }.add(channel)
        }

        val order = listOf("央视", "卫视", "地方", "港澳台", "📺央视频道", "📡卫视频道",
            "☘️北京频道", "☘️上海频道", "☘️天津频道", "☘️重庆频道", "☘️广东频道",
            "☘️浙江频道", "☘️江苏频道", "其他")

        return groupMap.entries
            .sortedBy { (key, _) ->
                order.indexOfFirst { key.contains(it) }.let { if (it == -1) order.size else it }
            }
            .map { ChannelGroup(it.key, it.value) }
    }
}
