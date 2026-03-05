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

# Ticket Counter (In a real bot, you'd save this to a file/database)
ticket_counter = 0

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

# --- Ticket Management Dropdown ---
class TicketManageMenu(discord.ui.Select):
    def __init__(self, owner_id):
        self.owner_id = owner_id
        options = [
            discord.SelectOption(label="Add Member", description="Add another user to this ticket", emoji="👤", value="add_user"),
            discord.SelectOption(label="Ping Owner", description="Notify the ticket owner in DMs", emoji="🔔", value="ping_owner")
        ]
        super().__init__(placeholder="Manage Ticket...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "add_user":
            await interaction.response.send_modal(AddUserModal())
        
        elif self.values[0] == "ping_owner":
            owner = interaction.guild.get_member(self.owner_id)
            if owner:
                try:
                    await owner.send(f"🔔 **Notification:** A staff member is waiting for you in your ticket: {interaction.channel.mention}")
                    await interaction.channel.send(f"🔔 {owner.mention}, check your DMs! A staff member notified you.")
                    await interaction.response.send_message("Owner notified via DM.", ephemeral=True)
                except:
                    await interaction.response.send_message("❌ Could not send DM to the owner (DMs closed).", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Owner not found in the server.", ephemeral=True)

# --- Ticket Control Panel ---
class TicketControl(discord.ui.View):
    def __init__(self, owner_id):
        super().__init__(timeout=None)
        self.owner_id = owner_id
        self.claimed_by = None
        # Adding the management dropdown menu
        self.add_item(TicketManageMenu(owner_id))

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.success, custom_id="claim_t", emoji="🙋‍♂️")
    async def claim_t(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff_role = discord.utils.get(interaction.guild.roles, name=STAFF_ROLE_NAME)
        if staff_role not in interaction.user.roles:
            return await interaction.response.send_message("Only staff can claim tickets!", ephemeral=True)
        self.claimed_by = interaction.user
        button.disabled = True
        button.label = f"Claimed by {interaction.user.display_name}"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"👤 **{interaction.user.mention}** has taken over this ticket.")

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="close_t", emoji="🔒")
    async def close_t(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Generating transcript and closing in 5 seconds...")
        
        # Transcript Logic
        transcript = f"--- Ticket Transcript: {interaction.channel.name} ---\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        async for m in interaction.channel.history(limit=None, oldest_first=True):
            transcript += f"[{m.created_at.strftime('%H:%M')}] {m.author}: {m.content}\n"
        
        file = discord.File(io.BytesIO(transcript.encode()), filename=f"transcript-{interaction.channel.name}.txt")
        log_ch = discord.utils.get(interaction.guild.text_channels, name=TICKET_LOG_CH)
        
        if log_ch:
            embed = discord.Embed(title="🔒 Ticket Closed", color=0xff0000, timestamp=datetime.now())
            embed.add_field(name="Ticket", value=interaction.channel.name, inline=True)
            embed.add_field(name="Staff", value=self.claimed_by.mention if self.claimed_by else "Unclaimed", inline=True)
            await log_ch.send(embed=embed, file=file)

        await asyncio.sleep(5)
        owner = interaction.guild.get_member(self.owner_id)
        if owner:
            try:
                view = FeedbackView(interaction.channel.name, self.claimed_by.display_name if self.claimed_by else "Support Team", interaction.guild.id)
                await owner.send("How was your experience?", view=view)
            except: pass
        await interaction.channel.delete()

# --- Dropdown for Categories ---
class TicketDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Support", description="Technical assistance", emoji="🛠️", value="Support"),
            discord.SelectOption(label="Reports", description="Report an issue", emoji="⚠️", value="Report"),
            discord.SelectOption(label="General", description="Questions", emoji="❓", value="General")
        ]
        super().__init__(placeholder="Select Category...", options=options)

    async def callback(self, interaction: discord.Interaction):
        global ticket_counter
        ticket_counter += 1
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

        # Ticket numbering: 📩-0001 format
        channel_name = f"📩-{ticket_counter:04d}"
        channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites, topic=f"OwnerID:{interaction.user.id}")

        embed = discord.Embed(title="Uun Support System", color=0xf3c1cf)
        embed.description = f"Welcome {interaction.user.mention},\nStaff will be with you shortly. Use the tools below to manage this ticket."
        
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

    embed = discord.Embed(title="📩 Support Hub", description="Select category to open a ticket.", color=0xf3c1cf)
    await ctx.send(embed=embed, view=TicketOpenView())
    await ctx.message.delete()

@bot.event
async def on_ready():
    bot.add_view(TicketOpenView())
    print(f"Uun Ticket Pro V3.5 | Online")

bot.run(os.getenv('DISCORD_TOKEN'))
