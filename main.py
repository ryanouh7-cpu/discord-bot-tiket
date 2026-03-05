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

ticket_counter = 0

# --- Star Rating System ---
class FeedbackView(discord.ui.View):
    def __init__(self, ticket_name, staff_member, guild_id):
        super().__init__(timeout=None)
        self.ticket_name, self.staff_member, self.guild_id = ticket_name, staff_member, guild_id

    async def send_rating(self, interaction: discord.Interaction, stars: int):
        guild = bot.get_guild(self.guild_id)
        feedback_ch = discord.utils.get(guild.text_channels, name=FEEDBACK_CH)
        if feedback_ch:
            embed = discord.Embed(title="⭐ Customer Satisfaction", color=0xf3c1cf, timestamp=datetime.now())
            embed.add_field(name="Assigned Staff", value=self.staff_member, inline=True)
            embed.add_field(name="Rating Score", value="⭐" * stars, inline=True)
            embed.set_footer(text=f"Ticket: {self.ticket_name}")
            await feedback_ch.send(embed=embed)
        await interaction.response.send_message("We appreciate your feedback!", ephemeral=True)
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

# --- Management Menu ---
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
            # Modal code would go here or call a function
            await interaction.response.send_message("Please use `!add [ID]` (Feature in development)", ephemeral=True)
        elif self.values[0] == "ping":
            owner = interaction.guild.get_member(self.owner_id)
            if owner:
                try: await owner.send(f"⚠️ Staff are waiting for you in {interaction.channel.mention}")
                except: pass
                await interaction.channel.send(f"🔔 {owner.mention}, please check this ticket!")
                await interaction.response.send_message("Owner notified.", ephemeral=True)

# --- Ticket Control ---
class TicketControl(discord.ui.View):
    def __init__(self, owner_id, open_time):
        super().__init__(timeout=None)
        self.owner_id = owner_id
        self.open_time = open_time
        self.claimed_by = None
        self.add_item(TicketManageMenu(owner_id))

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.success, emoji="🙋‍♂️")
    async def claim_t(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff_role = discord.utils.get(interaction.guild.roles, name=STAFF_ROLE_NAME)
        if staff_role not in interaction.user.roles:
            return await interaction.response.send_message("Authorized Staff only!", ephemeral=True)
        
        self.claimed_by = interaction.user
        button.disabled = True
        button.label = f"Claimed by {interaction.user.display_name}"
        
        # Unlock the channel for the specific staff member
        await interaction.channel.set_permissions(interaction.user, send_messages=True, view_channel=True)
        
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"✅ **{interaction.user.mention}** is now handling this ticket. Chat unlocked for staff.")

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close_t(self, interaction: discord.Interaction, button: discord.ui.Button):
        close_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        await interaction.response.send_message("Processing logs and closing...")

        transcript = f"Ticket: {interaction.channel.name}\nOpened: {self.open_time}\nClosed: {close_time}\nStaff: {self.claimed_by}\n\n"
        async for m in interaction.channel.history(limit=None, oldest_first=True):
            transcript += f"[{m.created_at.strftime('%H:%M')}] {m.author}: {m.content}\n"
        
        file = discord.File(io.BytesIO(transcript.encode()), filename=f"{interaction.channel.name}.txt")
        log_ch = discord.utils.get(interaction.guild.text_channels, name=TICKET_LOG_CH)
        
        if log_ch:
            embed = discord.Embed(title="Ticket Log Report", color=0xff0000, timestamp=datetime.now())
            embed.add_field(name="Ticket ID", value=interaction.channel.name, inline=True)
            embed.add_field(name="Opened At", value=self.open_time, inline=True)
            embed.add_field(name="Closed At", value=close_time, inline=True)
            embed.add_field(name="Handled By", value=self.claimed_by.mention if self.claimed_by else "None", inline=False)
            await log_ch.send(embed=embed, file=file)

        await asyncio.sleep(5)
        owner = interaction.guild.get_member(self.owner_id)
        if owner:
            try:
                view = FeedbackView(interaction.channel.name, self.claimed_by.display_name if self.claimed_by else "Uun Support", interaction.guild.id)
                await owner.send(f"Thank you for contacting Uun Support. How would you rate our service?", view=view)
            except: pass
        await interaction.channel.delete()

# --- Opening Dropdown ---
class TicketDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Technical Support", emoji="🛠️", value="Support"),
            discord.SelectOption(label="Reporting & Complaints", emoji="⚠️", value="Report"),
            discord.SelectOption(label="General Inquiries", emoji="❓", value="General")
        ]
        super().__init__(placeholder="Select a department to open a ticket...", options=options)

    async def callback(self, interaction: discord.Interaction):
        global ticket_counter
        ticket_counter += 1
        guild = interaction.guild
        staff_role = discord.utils.get(guild.roles, name=STAFF_ROLE_NAME)
        cat = discord.utils.get(guild.categories, name=TICKET_CAT_NAME)
        open_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Permissions: Staff can see but NOT send messages until claim
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=False)

        channel = await guild.create_text_channel(name=f"📩-{ticket_counter:04d}", category=cat, overwrites=overwrites, topic=f"OwnerID:{interaction.user.id}")

        embed = discord.Embed(title="Uun Official Support", color=0xf3c1cf)
        embed.description = (
            f"Greetings {interaction.user.mention},\n\n"
            "Thank you for reaching out to **Uun**. A staff member will be assigned to your case shortly.\n\n"
            "**Staff Instructions:** You must click **Claim** to enable your chat permissions in this channel."
        )
        embed.add_field(name="Ticket ID", value=f"#{ticket_counter:04d}", inline=True)
        embed.add_field(name="Category", value=self.values[0], inline=True)
        embed.set_footer(text="Uun Community • Efficiency & Quality")
        
        await channel.send(embed=embed, view=TicketControl(interaction.user.id, open_time))
        await interaction.response.send_message(f"Your ticket has been generated: {channel.mention}", ephemeral=True)

class TicketOpenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())

# --- Setup Command ---
@bot.command(name='tsetup')
@commands.has_permissions(administrator=True)
async def tsetup(ctx):
    embed = discord.Embed(
        title="📩 Uun Support Hub",
        description=(
            "Welcome to the **Uun Support Center**.\n\n"
            "To ensure the best experience, please select the most relevant department for your inquiry.\n"
            "• **Support:** Technical issues and server help.\n"
            "• **Reports:** Report a member or a violation.\n"
            "• **General:** Any other questions."
        ),
        color=0xf3c1cf
    )
    embed.set_image(url="https://googleusercontent.com/image_generation_content/17") # Placeholder for your banner
    embed.set_footer(text="Uun Community • Manifesting Excellence")
    await ctx.send(embed=embed, view=TicketOpenView())
    await ctx.message.delete()

@bot.event
async def on_ready():
    bot.add_view(TicketOpenView())
    print(f"Uun Ticket Pro V4.0 | Fully Integrated")

bot.run(os.getenv('DISCORD_TOKEN'))
