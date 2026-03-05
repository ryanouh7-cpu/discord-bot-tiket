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
            embed = discord.Embed(title="⭐ New Feedback Received", color=0xf3c1cf, timestamp=datetime.now())
            embed.add_field(name="Staff Member", value=self.staff_member, inline=True)
            embed.add_field(name="Rating", value="⭐" * stars, inline=True)
            embed.add_field(name="Ticket", value=self.ticket_name, inline=False)
            embed.set_footer(text=f"By: {interaction.user}", icon_url=interaction.user.display_avatar.url)
            await feedback_ch.send(embed=embed)
        await interaction.response.send_message("Thank you for your feedback!", ephemeral=True)
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
class AddUserModal(discord.ui.Modal, title="Add Member to Ticket"):
    user_id = discord.ui.TextInput(label="User ID", placeholder="Paste the User ID here...", min_length=15)
    async def on_submit(self, interaction: discord.Interaction):
        try:
            member = interaction.guild.get_member(int(self.user_id.value))
            if member:
                await interaction.channel.set_permissions(member, view_channel=True, send_messages=True)
                await interaction.response.send_message(f"✅ {member.mention} has been added to the ticket.", ephemeral=False)
            else:
                await interaction.response.send_message("❌ Member not found.", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid ID.", ephemeral=True)

# --- Ticket Control Panel ---
class TicketControl(discord.ui.View):
    def __init__(self, owner_id):
        super().__init__(timeout=None)
        self.owner_id = owner_id
        self.claimed_by = None

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.success, custom_id="claim_t", emoji="🙋‍♂️")
    async def claim_t(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff_role = discord.utils.get(interaction.guild.roles, name=STAFF_ROLE_NAME)
        if staff_role not in interaction.user.roles:
            return await interaction.response.send_message("Only staff can claim tickets!", ephemeral=True)
        self.claimed_by = interaction.user
        button.disabled = True
        button.label = f"Claimed by {interaction.user.display_name}"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"👤 **{interaction.user.mention}** has taken over this ticket and will assist you shortly.")

    @discord.ui.button(label="Add Member", style=discord.ButtonStyle.secondary, emoji="👤")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddUserModal())

    @discord.ui.button(label="Ping Owner", style=discord.ButtonStyle.primary, emoji="🔔")
    async def ping_owner(self, interaction: discord.Interaction, button: discord.ui.Button):
        owner = interaction.guild.get_member(self.owner_id)
        if owner:
            await interaction.channel.send(f"🔔 {owner.mention}, a staff member is waiting for your response!")
            await interaction.response.send_message("Owner notified.", ephemeral=True)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="close_t", emoji="🔒")
    async def close_t(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Generating transcript and closing in 5 seconds...")
        
        transcript = f"--- Ticket Transcript: {interaction.channel.name} ---\n"
        transcript += f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        transcript += f"Owner ID: {self.owner_id}\n"
        transcript += f"Claimed By: {self.claimed_by if self.claimed_by else 'None'}\n"
        transcript += "------------------------------------------\n"
        
        async for m in interaction.channel.history(limit=None, oldest_first=True):
            transcript += f"[{m.created_at.strftime('%H:%M')}] {m.author}: {m.content}\n"
        
        file = discord.File(io.BytesIO(transcript.encode()), filename=f"transcript-{interaction.channel.name}.txt")
        log_ch = discord.utils.get(interaction.guild.text_channels, name=TICKET_LOG_CH)
        
        if log_ch:
            embed = discord.Embed(title="🔒 Ticket Closed", color=0xff0000, timestamp=datetime.now())
            embed.add_field(name="Ticket Name", value=interaction.channel.name, inline=True)
            embed.add_field(name="Opened By", value=f"<@{self.owner_id}>", inline=True)
            embed.add_field(name="Closed By", value=interaction.user.mention, inline=True)
            embed.add_field(name="Staff Claimed", value=self.claimed_by.mention if self.claimed_by else "Unclaimed", inline=True)
            await log_ch.send(embed=embed, file=file)

        await asyncio.sleep(5)
        owner = interaction.guild.get_member(self.owner_id)
        if owner:
            try:
                view = FeedbackView(interaction.channel.name, self.claimed_by.display_name if self.claimed_by else "Support Team", interaction.guild.id)
                await owner.send(f"Your ticket **{interaction.channel.name}** has been closed. How was your experience?", view=view)
            except: pass
        await interaction.channel.delete()

# --- Dropdown for Categories ---
class TicketDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Support", description="Technical issues & assistance", emoji="🛠️", value="Support"),
            discord.SelectOption(label="Reports", description="Report a member or an issue", emoji="⚠️", value="Report"),
            discord.SelectOption(label="General", description="Questions & inquiries", emoji="❓", value="General")
        ]
        super().__init__(placeholder="Select the reason for your ticket...", options=options)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        staff_role = discord.utils.get(guild.roles, name=STAFF_ROLE_NAME)
        category = discord.utils.get(guild.categories, name=TICKET_CAT_NAME)
        
        if not category: category = await guild.create_category(TICKET_CAT_NAME)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        if staff_role: overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=f"{self.values[0]}-{interaction.user.name}",
            category=category, overwrites=overwrites,
            topic=f"OwnerID:{interaction.user.id}"
        )

        embed = discord.Embed(title="Uun Support System", color=0xf3c1cf)
        embed.description = f"Welcome {interaction.user.mention},\nOur staff will be with you shortly. Use the buttons below to manage this ticket."
        embed.add_field(name="Category", value=self.values[0], inline=True)
        embed.add_field(name="Opened At", value=datetime.now().strftime('%Y-%m-%d %H:%M'), inline=True)
        
        await channel.send(embed=embed, view=TicketControl(interaction.user.id))
        await interaction.response.send_message(f"Ticket created: {channel.mention}", ephemeral=True)

class TicketOpenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())

# --- Commands ---
@bot.command(name='tsetup')
@commands.has_permissions(administrator=True)
async def tsetup(ctx):
    log_cat = discord.utils.get(ctx.guild.categories, name=LOGS_CAT_NAME)
    if not discord.utils.get(ctx.guild.text_channels, name=FEEDBACK_CH):
        await ctx.guild.create_text_channel(FEEDBACK_CH, category=log_cat)
    if not discord.utils.get(ctx.guild.text_channels, name=TICKET_LOG_CH):
        await ctx.guild.create_text_channel(TICKET_LOG_CH, category=log_cat)

    embed = discord.Embed(title="📩 Help & Support Hub", description="Please select a category from the dropdown menu to open a support ticket.", color=0xf3c1cf)
    embed.set_footer(text="Uun Community")
    await ctx.send(embed=embed, view=TicketOpenView())
    await ctx.message.delete()

@bot.event
async def on_ready():
    bot.add_view(TicketOpenView())
    print(f"Uun Ticket System Pro V3.0 | Logged in as {bot.user}")

bot.run(os.getenv('DISCORD_TOKEN'))
