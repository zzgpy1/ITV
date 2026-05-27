package com.iptv.player

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.iptv.player.databinding.ItemChannelBinding

class ChannelAdapter(
    private val channels: List<MainActivity.Channel>,
    private val onItemClick: (MainActivity.Channel) -> Unit
) : RecyclerView.Adapter<ChannelAdapter.ViewHolder>() {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val binding = ItemChannelBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return ViewHolder(binding)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val channel = channels[position]
        holder.binding.channelName.text = channel.name
        holder.itemView.setOnClickListener { onItemClick(channel) }
    }

    override fun getItemCount() = channels.size

    class ViewHolder(val binding: ItemChannelBinding) : RecyclerView.ViewHolder(binding.root)
}
