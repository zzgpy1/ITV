package com.iptv.player

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.widget.ImageButton
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.google.android.exoplayer2.ExoPlayer
import com.google.android.exoplayer2.MediaItem
import com.google.android.exoplayer2.PlaybackException
import com.google.android.exoplayer2.Player
import com.google.android.exoplayer2.source.hls.HlsMediaSource
import com.google.android.exoplayer2.trackselection.DefaultTrackSelector
import com.google.android.exoplayer2.ui.PlayerView
import com.google.android.exoplayer2.upstream.DefaultHttpDataSource
import com.iptv.player.model.Channel

class PlayerActivity : AppCompatActivity() {

    private lateinit var playerView: PlayerView
    private var exoPlayer: ExoPlayer? = null
    private lateinit var channelListFragment: ChannelListFragment

    private lateinit var topBar: View
    private lateinit var channelNameText: TextView
    private lateinit var prevButton: ImageButton
    private lateinit var nextButton: ImageButton
    private lateinit var listButton: ImageButton

    private var controlsHandler = Handler(Looper.getMainLooper())
    private var isControlsVisible = true
    private var currentChannel: Channel? = null
    private var currentPosition = 0
    private var isPlayerPrepared = false

    private var touchStartY = 0f
    private val SWIPE_THRESHOLD = 100f

    companion object {
        private const val CONTROLS_HIDE_DELAY = 3000L
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_player)

        try {
            initViews()
            initChannelList()
            setupControls()
            setupTouchListener()
            initPlayer()

            if (DataManager.allChannels.isNotEmpty()) {
                currentPosition = 0
                playChannel(DataManager.allChannels[currentPosition])
            } else {
                Toast.makeText(this, "无频道数据，请返回重试", Toast.LENGTH_LONG).show()
                finish()
            }

            startControlsHideTimer()
        } catch (e: Exception) {
            e.printStackTrace()
            Toast.makeText(this, "初始化失败: ${e.message}", Toast.LENGTH_LONG).show()
            finish()
        }
    }

    private fun initViews() {
        playerView = findViewById(R.id.player_view)
        topBar = findViewById(R.id.top_bar)
        channelNameText = findViewById(R.id.channel_name)
        prevButton = findViewById(R.id.btn_prev)
        nextButton = findViewById(R.id.btn_next)
        listButton = findViewById(R.id.btn_list)
    }

    private fun initPlayer() {
        try {
            val trackSelector = DefaultTrackSelector(this).apply {
                setParameters(buildUponParameters().setMaxVideoSize(1920, 1080))
            }

            exoPlayer = ExoPlayer.Builder(this)
                .setTrackSelector(trackSelector)
                .build()

            playerView.player = exoPlayer

            exoPlayer?.addListener(object : Player.Listener {
                override fun onPlaybackStateChanged(playbackState: Int) {
                    when (playbackState) {
                        Player.STATE_READY -> {
                            isPlayerPrepared = true
                        }
                        Player.STATE_ENDED -> {
                            // 自动播放下一个
                            nextChannel()
                        }
                    }
                }

                override fun onPlayerError(error: PlaybackException) {
                    Toast.makeText(this@PlayerActivity, "播放失败，尝试下一个频道", Toast.LENGTH_SHORT).show()
                    nextChannel()
                }
            })
        } catch (e: Exception) {
            e.printStackTrace()
            Toast.makeText(this, "播放器初始化失败: ${e.message}", Toast.LENGTH_LONG).show()
        }
    }

    private fun initChannelList() {
        channelListFragment = ChannelListFragment()
        channelListFragment.setOnChannelSelectedListener { channel, position ->
            currentPosition = position
            playChannel(channel)
        }

        supportFragmentManager.beginTransaction()
            .add(R.id.channel_list_container, channelListFragment)
            .commit()

        channelListFragment.hide()
    }

    private fun setupControls() {
        prevButton.setOnClickListener {
            previousChannel()
            resetControlsHideTimer()
        }

        nextButton.setOnClickListener {
            nextChannel()
            resetControlsHideTimer()
        }

        listButton.setOnClickListener {
            toggleChannelList()
            resetControlsHideTimer()
        }

        playerView.setOnClickListener {
            toggleControls()
        }
    }

    private fun setupTouchListener() {
        playerView.setOnTouchListener { _, event ->
            try {
                when (event.action) {
                    MotionEvent.ACTION_DOWN -> {
                        touchStartY = event.y
                        true
                    }
                    MotionEvent.ACTION_UP -> {
                        val diffY = touchStartY - event.y
                        if (Math.abs(diffY) > SWIPE_THRESHOLD) {
                            if (diffY > 0) {
                                previousChannel()
                            } else {
                                nextChannel()
                            }
                            resetControlsHideTimer()
                        }
                        true
                    }
                    else -> false
                }
            } catch (e: Exception) {
                false
            }
        }
    }

    private fun playChannel(channel: Channel) {
        try {
            currentChannel = channel
            channelNameText.text = channel.name

            val mediaItem = MediaItem.Builder()
                .setUri(channel.url)
                .setMimeType("application/x-mpegURL")
                .build()

            val dataSourceFactory = DefaultHttpDataSource.Factory()
                .setUserAgent("IPTVPlayer/1.0")

            val hlsMediaSource = HlsMediaSource.Factory(dataSourceFactory)
                .createMediaSource(mediaItem)

            exoPlayer?.setMediaSource(hlsMediaSource)
            exoPlayer?.prepare()
            exoPlayer?.play()

            channelListFragment.updateSelectedPosition(currentPosition)
            isPlayerPrepared = false
        } catch (e: Exception) {
            e.printStackTrace()
            Toast.makeText(this, "播放失败: ${e.message}", Toast.LENGTH_SHORT).show()
            nextChannel()
        }
    }

    private fun previousChannel() {
        if (DataManager.allChannels.isEmpty()) return
        currentPosition--
        if (currentPosition < 0) {
            currentPosition = DataManager.allChannels.size - 1
        }
        playChannel(DataManager.allChannels[currentPosition])
        showControls()
        resetControlsHideTimer()
    }

    private fun nextChannel() {
        if (DataManager.allChannels.isEmpty()) return
        currentPosition++
        if (currentPosition >= DataManager.allChannels.size) {
            currentPosition = 0
        }
        playChannel(DataManager.allChannels[currentPosition])
        showControls()
        resetControlsHideTimer()
    }

    private fun toggleControls() {
        if (isControlsVisible) {
            hideControls()
        } else {
            showControls()
        }
    }

    private fun showControls() {
        topBar.visibility = View.VISIBLE
        isControlsVisible = true
        startControlsHideTimer()
    }

    private fun hideControls() {
        topBar.visibility = View.GONE
        isControlsVisible = false
        controlsHandler.removeCallbacksAndMessages(null)
    }

    private fun toggleChannelList() {
        if (channelListFragment.isListVisible()) {
            channelListFragment.hide()
        } else {
            channelListFragment.show()
            hideControls()
        }
    }

    private fun startControlsHideTimer() {
        controlsHandler.removeCallbacksAndMessages(null)
        controlsHandler.postDelayed({
            if (isControlsVisible && !channelListFragment.isListVisible()) {
                hideControls()
            }
        }, CONTROLS_HIDE_DELAY)
    }

    private fun resetControlsHideTimer() {
        startControlsHideTimer()
    }

    override fun onResume() {
        super.onResume()
        exoPlayer?.play()
    }

    override fun onPause() {
        super.onPause()
        exoPlayer?.pause()
    }

    override fun onDestroy() {
        super.onDestroy()
        exoPlayer?.release()
        exoPlayer = null
        controlsHandler.removeCallbacksAndMessages(null)
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        return when (keyCode) {
            KeyEvent.KEYCODE_DPAD_UP -> {
                previousChannel()
                true
            }
            KeyEvent.KEYCODE_DPAD_DOWN -> {
                nextChannel()
                true
            }
            KeyEvent.KEYCODE_DPAD_CENTER, KeyEvent.KEYCODE_ENTER -> {
                toggleControls()
                true
            }
            KeyEvent.KEYCODE_MENU -> {
                toggleChannelList()
                true
            }
            else -> super.onKeyDown(keyCode, event)
        }
    }
}
