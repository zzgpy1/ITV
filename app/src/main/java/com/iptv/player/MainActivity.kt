package com.iptv.player

import android.os.Build
import android.os.Bundle
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.cardview.widget.CardView
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.exoplayer2.MediaItem
import com.google.android.exoplayer2.SimpleExoPlayer
import com.google.android.exoplayer2.source.hls.HlsMediaSource
import com.google.android.exoplayer2.trackselection.DefaultTrackSelector
import com.google.android.exoplayer2.ui.PlayerView
import com.google.android.exoplayer2.upstream.DefaultHttpDataSource
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit
import kotlin.math.abs

class MainActivity : AppCompatActivity() {

    private lateinit var playerView: PlayerView
    private lateinit var loadingSpinner: ProgressBar
    private lateinit var errorText: TextView
    private lateinit var channelList: RecyclerView
    private lateinit var drawerContainer: CardView
    private var exoPlayer: SimpleExoPlayer? = null
    private var currentChannelUrl: String? = null
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()
    private var drawerY = 0f
    private var downY = 0f
    private var isDragging = false

    override fun onCreate(savedInstanceState: Bundle?) {
        // 全屏沉浸式设置
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            window.insetsController?.hide(android.view.WindowInsets.Type.statusBars() or android.view.WindowInsets.Type.navigationBars())
            window.insetsController?.systemBarsBehavior = android.view.WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        } else {
            @Suppress("DEPRECATION")
            window.decorView.systemUiVisibility = (
                View.SYSTEM_UI_FLAG_FULLSCREEN or
                View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or
                View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
                View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
            )
        }
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        playerView = findViewById(R.id.player_view)
        loadingSpinner = findViewById(R.id.loading_spinner)
        errorText = findViewById(R.id.error_text)
        channelList = findViewById(R.id.channel_list)
        drawerContainer = findViewById(R.id.drawer_container)

        channelList.layoutManager = LinearLayoutManager(this)

        // 抽屉滑动处理
        drawerContainer.setOnTouchListener { _, event ->
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    downY = event.rawY
                    drawerY = drawerContainer.translationY
                    isDragging = true
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    if (isDragging) {
                        val delta = event.rawY - downY
                        var newY = drawerY + delta
                        newY = newY.coerceIn(0f, drawerContainer.height.toFloat())
                        drawerContainer.translationY = newY
                        true
                    } else false
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    isDragging = false
                    // 自动回弹：如果滑动超过一半则隐藏，否则恢复原位
                    val halfHeight = drawerContainer.height / 2f
                    if (drawerContainer.translationY > halfHeight) {
                        drawerContainer.animate().translationY(drawerContainer.height.toFloat()).start()
                    } else {
                        drawerContainer.animate().translationY(0f).start()
                    }
                    true
                }
                else -> false
            }
        }

        // 点击视频区域时显示/隐藏频道列表
        playerView.setOnClickListener {
            if (drawerContainer.translationY == 0f) {
                drawerContainer.animate().translationY(drawerContainer.height.toFloat()).start()
            } else {
                drawerContainer.animate().translationY(0f).start()
            }
        }

        // 加载播放列表
        val baseUrl = BuildConfig.BASE_URL
        val normalizedBase = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
        val m3uUrl = "${normalizedBase}tv.m3u"
        val txtUrl = "${normalizedBase}tv.txt"

        loadPlaylist(m3uUrl, true) { success ->
            if (!success) {
                loadPlaylist(txtUrl, false) { txtSuccess ->
                    if (!txtSuccess) {
                        runOnUiThread {
                            loadingSpinner.visibility = View.GONE
                            errorText.text = "无法加载播放列表\n$m3uUrl\n$txtUrl"
                            errorText.visibility = View.VISIBLE
                        }
                    }
                }
            }
        }
    }

    private fun loadPlaylist(url: String, isM3u: Boolean, callback: (Boolean) -> Unit) {
        runOnUiThread {
            loadingSpinner.visibility = View.VISIBLE
            errorText.visibility = View.GONE
        }

        Thread {
            try {
                val request = Request.Builder().url(url).build()
                val response = client.newCall(request).execute()
                if (!response.isSuccessful) {
                    callback(false)
                    return@Thread
                }
                val content = response.body?.string() ?: ""
                val channels = if (isM3u) parseM3u(content) else parseTxt(content)
                runOnUiThread {
                    loadingSpinner.visibility = View.GONE
                    if (channels.isEmpty()) {
                        errorText.text = "未找到任何频道"
                        errorText.visibility = View.VISIBLE
                        callback(false)
                    } else {
                        setupChannelList(channels)
                        playChannel(channels[0].url)
                        callback(true)
                    }
                }
            } catch (e: Exception) {
                e.printStackTrace()
                runOnUiThread {
                    loadingSpinner.visibility = View.GONE
                    errorText.text = "加载失败: ${e.message}"
                    errorText.visibility = View.VISIBLE
                }
                callback(false)
            }
        }.start()
    }

    private fun parseM3u(content: String): List<Channel> {
        val channels = mutableListOf<Channel>()
        var currentName = ""
        content.lines().forEach { line ->
            val trimmed = line.trim()
            when {
                trimmed.startsWith("#EXTINF") -> {
                    val idx = trimmed.lastIndexOf(",")
                    if (idx != -1) currentName = trimmed.substring(idx + 1).trim()
                }
                trimmed.startsWith("http") && currentName.isNotEmpty() -> {
                    channels.add(Channel(currentName, trimmed))
                    currentName = ""
                }
            }
        }
        return channels
    }

    private fun parseTxt(content: String): List<Channel> {
        val channels = mutableListOf<Channel>()
        content.lines().forEach { line ->
            val trimmed = line.trim()
            if (trimmed.isNotEmpty() && !trimmed.startsWith("#")) {
                val comma = trimmed.indexOf(',')
                if (comma > 0) {
                    val name = trimmed.substring(0, comma)
                    val url = trimmed.substring(comma + 1)
                    if (url.startsWith("http")) channels.add(Channel(name, url))
                }
            }
        }
        return channels
    }

    private fun setupChannelList(channels: List<Channel>) {
        val adapter = ChannelAdapter(channels) { channel ->
            playChannel(channel.url)
        }
        channelList.adapter = adapter
        // 设置默认选中第一项
        channelList.post {
            val firstView = channelList.layoutManager?.findViewByPosition(0)
            firstView?.requestFocus()
        }
    }

    private fun playChannel(url: String) {
        if (currentChannelUrl == url && exoPlayer?.isPlaying == true) return
        currentChannelUrl = url
        releasePlayer()
        val trackSelector = DefaultTrackSelector(this)
        exoPlayer = SimpleExoPlayer.Builder(this).setTrackSelector(trackSelector).build()
        playerView.player = exoPlayer
        val mediaSource = HlsMediaSource.Factory(DefaultHttpDataSource.Factory())
            .createMediaSource(MediaItem.fromUri(url))
        exoPlayer?.setMediaSource(mediaSource)
        exoPlayer?.prepare()
        exoPlayer?.playWhenReady = true
        // 提示当前播放频道
        val channelName = (channelList.adapter as? ChannelAdapter)?.let { adapter ->
            // 简单提示
            Toast.makeText(this, "正在播放", Toast.LENGTH_SHORT).show()
        }
    }

    private fun releasePlayer() {
        exoPlayer?.release()
        exoPlayer = null
        playerView.player = null
    }

    override fun onDestroy() {
        super.onDestroy()
        releasePlayer()
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) {
            // 重新进入全屏
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                window.insetsController?.hide(android.view.WindowInsets.Type.statusBars() or android.view.WindowInsets.Type.navigationBars())
            } else {
                @Suppress("DEPRECATION")
                window.decorView.systemUiVisibility = (
                    View.SYSTEM_UI_FLAG_FULLSCREEN or
                    View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
                    View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                )
            }
        }
    }

    data class Channel(val name: String, val url: String)
}
