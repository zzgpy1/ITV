package com.example.tvplayer

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.example.tvplayer.data.PlaylistParser
import com.example.tvplayer.ui.screens.PlaylistScreen
import com.example.tvplayer.ui.screens.PlayerScreen
import com.example.tvplayer.ui.theme.TVPlayerTheme
import com.example.tvplayer.ui.theme.TvTheme
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // 预加载播放列表
        CoroutineScope(Dispatchers.IO).launch {
            PlaylistParser.loadPlaylist()
        }
        
        setContent {
            val isTv = packageManager.hasSystemFeature(android.content.pm.PackageManager.FEATURE_LEANBACK)
            
            if (isTv) {
                TvTheme {
                    NavigationHost(isTv = true)
                }
            } else {
                TVPlayerTheme {
                    Surface(
                        modifier = Modifier.fillMaxSize(),
                        color = MaterialTheme.colorScheme.background
                    ) {
                        NavigationHost(isTv = false)
                    }
                }
            }
        }
    }
}

@Composable
fun NavigationHost(isTv: Boolean) {
    val navController = rememberNavController()
    
    NavHost(
        navController = navController,
        startDestination = "playlist"
    ) {
        composable("playlist") {
            PlaylistScreen(
                onChannelSelected = { channelId ->
                    navController.navigate("player/$channelId")
                },
                isTv = isTv
            )
        }
        composable(
            "player/{channelId}",
            arguments = listOf(navArgument("channelId") { type = NavType.IntType })
        ) { backStackEntry ->
            val channelId = backStackEntry.arguments?.getInt("channelId") ?: 0
            PlayerScreen(
                channelId = channelId,
                onBack = { navController.popBackStack() },
                isTv = isTv
            )
        }
    }
}
