import discord
from discord.ext import commands
import os
import asyncio
import io
from datetime import datetime

# --- 1. Bot Setup ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# --- 2. Configuration ---
STAFF_ROLE_NAME = "Staff"
LOGS_CAT_NAME = "Uun Logs"
FEEDBACK_CH = "feedback"
TICKET_LOG_CH = "ticket-logs"
TICKET_CAT_NAME = "Tickets"

ticket_counter = 0

# --- 3. Star Rating System (Feedback Log) ---
class FeedbackView(discord.ui.View):
    def __init__(self, ticket_name, staff_mention, guild_id, owner_mention):
        super().__init__(timeout=None)
        self.ticket_name = ticket_name
        self.staff_mention = staff_mention
        self.guild_id = guild_id
        self.owner_mention = owner_mention

    async def send_rating(self, interaction: discord.Interaction, stars: int):
        guild = bot.get_guild(self.guild_id)
        feedback_ch = discord.utils.get(guild.text_channels, name=FEEDBACK_CH)
        if feedback_ch:
            embed = discord.Embed(title="⭐ New Service Rating", color=0xf3c1cf, timestamp=datetime.now())
            embed.add_field(name="Staff Handled", value=self.staff_mention, inline=True)
            embed.add_field(name="Customer", value=self.owner_mention, inline=True)
            embed.add_field(name="Rating Score", value="⭐" * stars, inline=True)
            embed.add_field(name="Ticket Source", value=f"`{self.ticket_name}`", inline=False)
            embed.set_footer(text="Uun Feedback System")
            await feedback_ch.send(embed=embed)
        await interaction.response.send_message("✅ Thank you for your feedback!", ephemeral=True)
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

# --- 4. Ticket Management Tools ---
class TicketManageMenu(discord.ui.Select):
    def __init__(self, owner_id):
        self.owner_id = owner_id
        options = [
            discord.SelectOption(label="Add Member", emoji="👤", value="add"),
            discord.SelectOption(label="Ping Owner", emoji="🔔", value="ping")
        ]
        super().__init__(placeholder="Administrative Tools...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "add":
            await interaction.response.send_modal(AddUserModal())
        elif self.values[0] == "ping":
            owner = interaction.guild.get_member(self.owner_id)
            if owner:
                try: await owner.send(f"⚠️ Staff are waiting for you in {interaction.channel.mention}")
                except: pass
                await interaction.channel.send(f"🔔 {owner.mention}, check your DMs! Staff are waiting.")
                await interaction.response.send_message("Owner notified.", ephemeral=True)

class AddUserModal(discord.ui.Modal, title="Add Member"):
    user_id = discord.ui.TextInput(label="User ID", placeholder="Paste ID here...")
    async def on_submit(self, interaction: discord.Interaction):
        try:
            member = interaction.guild.get_member(int(self.user_id.value))
            if member:
                await interaction.channel.set_permissions(member, view_channel=True, send_messages=True)
                await interaction.response.send_message(f"✅ {member.mention} added.")
            else: await interaction.response.send_message("User not found.", ephemeral=True)
        except: await interaction.response.send_message("Invalid ID.", ephemeral=True)

# --- 5. Ticket Control & Logs ---
class TicketControl(discord.ui.View):
    def __init__(self, owner_id, open_time):
        super().__init__(timeout=None)
        self.owner_id, self.open_time, self.claimed_by = owner_id, open_time, None
        self.add_item(TicketManageMenu(owner_id))

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.success, emoji="🙋‍♂️")
    async def claim_t(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff_role = discord.utils.get(interaction.guild.roles, name=STAFF_ROLE_NAME)
        if staff_role not in interaction.user.roles:
            return await interaction.response.send_message("Staff only!", ephemeral=True)
        
        self.claimed_by = interaction.user
        button.disabled, button.label = True, f"Claimed by {interaction.user.display_name}"
        await interaction.channel.set_permissions(interaction.user, send_messages=True, view_channel=True)
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"✅ {interaction.user.mention} is now handling this ticket.")

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close_t(self, interaction: discord.Interaction, button: discord.ui.Button):
        close_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        await interaction.response.send_message("Generating logs and closing...")
        
        transcript = f"Ticket: {interaction.channel.name}\nOpened: {self.open_time}\nClosed: {close_time}\nStaff: {self.claimed_by}\n\n"
        async for m in interaction.channel.history(limit=None, oldest_first=True):
            transcript += f"[{m.created_at.strftime('%H:%M')}] {m.author}: {m.content}\n"
        
        file = discord.File(io.BytesIO(transcript.encode()), filename=f"{interaction.channel.name}.txt")
        log_ch = discord.utils.get(interaction.guild.text_channels, name=TICKET_LOG_CH)
        if log_ch:
            embed = discord.Embed(title="🔒 Ticket Closed", color=0xff0000, timestamp=datetime.now())
            embed.add_field(name="ID", value=interaction.channel.name, inline=True)
            embed.add_field(name="Opened At", value=self.open_time, inline=True)
            embed.add_field(name="Closed At", value=close_time, inline=True)
            embed.add_field(name="Staff", value=self.claimed_by.mention if self.claimed_by else "None", inline=False)
            await log_ch.send(embed=embed, file=file)

        owner = interaction.guild.get_member(self.owner_id)
        if owner:
            try:
                view = FeedbackView(interaction.channel.name, self.claimed_by.mention if self.claimed_by else "Support", interaction.guild.id, owner.mention)
                await owner.send(f"Thank you for contacting **{interaction.guild.name}**. How was our service?", view=view)
            except: pass
        await asyncio.sleep(5)
        await interaction.channel.delete()

# --- 6. Dropdown System ---
class TicketDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Support", emoji="🛠️", value="Support"),
            discord.SelectOption(label="Reports", emoji="⚠️", value="Report"),
            discord.SelectOption(label="General", emoji="❓", value="General")
        ]
        super().__init__(placeholder="Select Category...", options=options)

    async def callback(self, interaction: discord.Interaction):
        global ticket_counter
        ticket_counter += 1
        guild, staff = interaction.guild, discord.utils.get(interaction.guild.roles, name=STAFF_ROLE_NAME)
        cat = discord.utils.get(guild.categories, name=TICKET_CAT_NAME)
        open_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        if staff: overwrites[staff] = discord.PermissionOverwrite(view_channel=True, send_messages=False) 

        ch = await guild.create_text_channel(name=f"📩-{ticket_counter:04d}", category=cat, overwrites=overwrites, topic=f"OwnerID:{interaction.user.id}")
        
        embed = discord.Embed(title="Uun Official Support", description=f"Greetings {interaction.user.mention},\nStaff will assist you shortly.\n\n**Staff:** Click **Claim** to unlock chat.", color=0xf3c1cf)
        await ch.send(embed=embed, view=TicketControl(interaction.user.id, open_time))
        await interaction.response.send_message(f"Ticket: {ch.mention}", ephemeral=True)

class TicketOpenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())

# --- 7. Main Commands ---
@bot.command()
@commands.has_permissions(administrator=True)
async def tsetup(ctx):
    log_cat = discord.utils.get(ctx.guild.categories, name=LOGS_CAT_NAME)
    if not log_cat: log_cat = await ctx.guild.create_category(LOGS_CAT_NAME)
    
    if not discord.utils.get(ctx.guild.text_channels, name=FEEDBACK_CH): await ctx.guild.create_text_channel(FEEDBACK_CH, category=log_cat)
    if not discord.utils.get(ctx.guild.text_channels, name=TICKET_LOG_CH): await ctx.guild.create_text_channel(TICKET_LOG_CH, category=log_cat)
    
    embed = discord.Embed(title="📩 Uun Support Hub", description="Select a category below to open a ticket.", color=0xf3c1cf)
    embed.set_footer(text="Uun Community")
    await ctx.send(embed=embed, view=TicketOpenView())
    await ctx.message.delete()

@bot.event
async def on_ready():
    bot.add_view(TicketOpenView())
    print(f"Uun Ticket Pro Online | No Verification Mode")

bot.run(os.getenv('DISCORD_TOKEN'))
