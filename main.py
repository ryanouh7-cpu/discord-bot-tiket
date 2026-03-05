import discord
from discord.ext import commands
import os
import asyncio
import io
from datetime import datetime

# Bot Setup
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Configuration
LOGS_CAT_NAME = "Uun Logs"
FEEDBACK_CH = "feedback"
TICKET_LOG_CH = "ticket-logs"
TICKET_CAT_NAME = "Tickets"
STAFF_ROLE_NAME = "Staff"

# Ticket Counter
ticket_count = 0

# --- Star Rating System (1-5 Stars) ---
class FeedbackView(discord.ui.View):
    def __init__(self, ticket_name, staff_member, guild_id):
        super().__init__(timeout=None)
        self.ticket_name = ticket_name
        self.staff_member = staff_member
        self.guild_id = guild_id

    async def send_rating(self, interaction: discord.Interaction, stars: int):
        guild = bot.get_guild(self.guild_id)
        feedback_ch = discord.utils.get(guild.text_channels, name=FEEDBACK_CH)
        if feedback_ch:
            embed = discord.Embed(title="⭐ New Feedback", color=0xf3c1cf, timestamp=datetime.now())
            embed.add_field(name="Staff", value=self.staff_member, inline=True)
            embed.add_field(name="Rating", value="⭐" * stars, inline=True)
            embed.set_footer(text=f"By: {interaction.user}")
            await feedback_ch.send(embed=embed)
        await interaction.response.send_message("Thanks!", ephemeral=True)
        self.stop()

    @discord.ui.button(label="1⭐", style=discord.ButtonStyle.gray)
    async def s1(self, it, btn): await self.send_rating(it, 1)
    @discord.ui.button(label="2⭐", style=discord.ButtonStyle.gray)
    async def s2(self, it, btn): await self.send_rating(it, 2)
    @discord.ui.button(label="3⭐", style=discord.ButtonStyle.gray)
    async def s3(self, it, btn): await self.send_rating(it, 3)
    @discord.ui.button(label="4⭐", style=discord.ButtonStyle.gray)
    async def s4(self, it, btn): await self.send_rating(it, 4)
    @discord.ui.button(label="5⭐", style=discord.ButtonStyle.gray)
    async def s5(self, it, btn): await self.send_rating(it, 5)

# --- Modal to Add User ---
class AddUserModal(discord.ui.Modal, title="Add Member"):
    user_id = discord.ui.TextInput(label="User ID", placeholder="Paste User ID here...")
    async def on_submit(self, interaction: discord.Interaction):
        try:
            member = interaction.guild.get_member(int(self.user_id.value))
            if member:
                await interaction.channel.set_permissions(member, view_channel=True, send_messages=True)
                await interaction.response.send_message(f"✅ Added {member.mention}", ephemeral=False)
            else: await interaction.response.send_message("Member not found.", ephemeral=True)
        except: await interaction.response.send_message("Invalid ID.", ephemeral=True)

# --- Management Dropdown (Inside Ticket) ---
class TicketActions(discord.ui.Select):
    def __init__(self, owner_id):
        self.owner_id = owner_id
        options = [
            discord.SelectOption(label="Add Member", emoji="👤", description="Add another user to this ticket"),
            discord.SelectOption(label="Ping Owner", emoji="🔔", description="Notify the owner via DM and mention")
        ]
        super().__init__(placeholder="Ticket Management Options...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "Add Member":
            await interaction.response.send_modal(AddUserModal())
        elif self.values[0] == "Ping Owner":
            owner = interaction.guild.get_member(self.owner_id)
            if owner:
                try: await owner.send(f"⚠️ **Reminder:** Staff are waiting for you in your ticket: {interaction.channel.mention}")
                except: pass
                await interaction.channel.send(f"🔔 {owner.mention}, check your DMs! Staff are waiting.")
                await interaction.response.send_message("Owner notified.", ephemeral=True)

# --- Main Ticket Control ---
class TicketControl(discord.ui.View):
    def __init__(self, owner_id):
        super().__init__(timeout=None)
        self.owner_id = owner_id
        self.claimed_by = None
        self.add_item(TicketActions(owner_id))

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.success, emoji="🙋‍♂️")
    async def claim_t(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff_role = discord.utils.get(interaction.guild.roles, name=STAFF_ROLE_NAME)
        if staff_role not in interaction.user.roles:
            return await interaction.response.send_message("Staff only!", ephemeral=True)
        self.claimed_by = interaction.user
        button.disabled = True
        button.label = f"Claimed by {interaction.user.display_name}"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"👤 **{interaction.user.mention}** will assist you.")

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close_t(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Closing in 5 seconds...")
        transcript = f"Ticket Log: {interaction.channel.name}\nOwner ID: {self.owner_id}\n"
        async for m in interaction.channel.history(limit=None, oldest_first=True):
            transcript += f"[{m.created_at.strftime('%H:%M')}] {m.author}: {m.content}\n"
        
        file = discord.File(io.BytesIO(transcript.encode()), filename=f"{interaction.channel.name}.txt")
        log_ch = discord.utils.get(interaction.guild.text_channels, name=TICKET_LOG_CH)
        if log_ch:
            embed = discord.Embed(title="🔒 Closed", color=0xff0000, timestamp=datetime.now())
            embed.add_field(name="By", value=interaction.user.mention)
            await log_ch.send(embed=embed, file=file)

        await asyncio.sleep(5)
        owner = interaction.guild.get_member(self.owner_id)
        if owner:
            try:
                view = FeedbackView(interaction.channel.name, self.claimed_by.display_name if self.claimed_by else "Support", interaction.guild.id)
                await owner.send("Please rate our support:", view=view)
            except: pass
        await interaction.channel.delete()

# --- Opening System ---
class TicketDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Support", emoji="🛠️", value="Support"),
            discord.SelectOption(label="Reports", emoji="⚠️", value="Report")
        ]
        super().__init__(placeholder="Choose a category...", options=options)

    async def callback(self, interaction: discord.Interaction):
        global ticket_count
        ticket_count += 1
        guild = interaction.guild
        staff = discord.utils.get(guild.roles, name=STAFF_ROLE_NAME)
        cat = discord.utils.get(guild.categories, name=TICKET_CAT_NAME)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        if staff: overwrites[staff] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=f"📩-{ticket_count:04d}", # مثال: 📩-0001
            category=cat, overwrites=overwrites,
            topic=f"OwnerID:{interaction.user.id}"
        )

        embed = discord.Embed(title="Uun Support", description=f"Welcome {interaction.user.mention}, staff will be here soon.", color=0xf3c1cf)
        await channel.send(embed=embed, view=TicketControl(interaction.user.id))
        await interaction.response.send_message(f"Created: {channel.mention}", ephemeral=True)

class TicketOpenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())

@bot.command()
@commands.has_permissions(administrator=True)
async def tsetup(ctx):
    embed = discord.Embed(title="📩 Support Hub", description="Select a category to open a ticket.", color=0xf3c1cf)
    await ctx.send(embed=embed, view=TicketOpenView())
    await ctx.message.delete()

@bot.event
async def on_ready():
    bot.add_view(TicketOpenView())
    print(f"Uun Ticket Pro Online!")

bot.run(os.getenv('DISCORD_TOKEN'))
