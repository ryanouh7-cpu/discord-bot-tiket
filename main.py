import discord
from discord.ext import commands
import os
import asyncio
import io
from datetime import datetime

# إعدادات البوت
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# الثوابت
LOGS_CAT = "Uun Logs"
FEEDBACK_CH = "feedback"
TICKET_LOG_CH = "ticket-logs"
TICKET_CAT = "Tickets"
STAFF_ROLE = "Staff"

# قاعدة بيانات وهمية للإحصائيات (تصفر عند إعادة تشغيل البوت)
staff_stats = {}

# --- نظام التقييم ---
class FeedbackView(discord.ui.View):
    def __init__(self, ticket_name, staff_member, guild_id):
        super().__init__(timeout=None)
        self.ticket_name = ticket_name
        self.staff_member = staff_member
        self.guild_id = guild_id

    async def send_rating(self, interaction: discord.Interaction, stars: int):
        guild = bot.get_guild(self.guild_id)
        feedback_channel = discord.utils.get(guild.text_channels, name=FEEDBACK_CH)
        if feedback_channel:
            embed = discord.Embed(title="⭐ تقييم جديد", color=0xf3c1cf, timestamp=datetime.now())
            embed.add_field(name="الموظف", value=self.staff_member)
            embed.add_field(name="التقييم", value="⭐" * stars)
            embed.set_footer(text=f"بواسطة: {interaction.user}")
            await feedback_channel.send(embed=embed)
        await interaction.response.send_message("شكراً لتقييمك!", ephemeral=True)
        self.stop()

    @discord.ui.button(label="1 ⭐", style=discord.ButtonStyle.gray)
    async def s1(self, it, btn): await self.send_rating(it, 1)
    @discord.ui.button(label="5 ⭐", style=discord.ButtonStyle.success)
    async def s5(self, it, btn): await self.send_rating(it, 5)

# --- لوحة التحكم داخل التيكت (Claim, Add, Close) ---
class TicketControl(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.claimed_by = None

    @discord.ui.button(label="Claim 🙋‍♂️", style=discord.ButtonStyle.success, custom_id="claim_t")
    async def claim_t(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff_role = discord.utils.get(interaction.guild.roles, name=STAFF_ROLE)
        if staff_role not in interaction.user.roles:
            return await interaction.response.send_message("هذا الزر للموظفين فقط!", ephemeral=True)
        
        self.claimed_by = interaction.user
        button.disabled = True
        button.label = f"استلمها: {interaction.user.display_name}"
        
        # تحديث الإحصائيات
        staff_stats[interaction.user.id] = staff_stats.get(interaction.user.id, 0) + 1
        
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"👤 الموظف {interaction.user.mention} سيقوم بمساعدتك الآن.")

    @discord.ui.button(label="Close 🔒", style=discord.ButtonStyle.danger, custom_id="close_t")
    async def close_t(self, interaction: discord.Interaction, button: discord.ui.Button):
        # حفظ Transcript
        transcript = ""
        async for m in interaction.channel.history(limit=None, oldest_first=True):
            transcript += f"[{m.created_at.strftime('%H:%M')}] {m.author}: {m.content}\n"
        
        file = discord.File(io.BytesIO(transcript.encode()), filename=f"log-{interaction.channel.name}.txt")
        log_ch = discord.utils.get(interaction.guild.text_channels, name=TICKET_LOG_CH)
        
        if log_ch:
            embed = discord.Embed(title="🔒 تذكرة مغلقة", color=discord.Color.red(), timestamp=datetime.now())
            embed.add_field(name="التذكرة", value=interaction.channel.name)
            embed.add_field(name="بواسطة", value=interaction.user.mention)
            await log_ch.send(embed=embed, file=file)

        await interaction.response.send_message("سيتم الإغلاق خلال ثواني...")
        await asyncio.sleep(3)
        
        user_id = int(interaction.channel.topic.split(":")[1])
        user = interaction.guild.get_member(user_id)
        if user:
            try:
                view = FeedbackView(interaction.channel.name, self.claimed_by.display_name if self.claimed_by else "Support", interaction.guild.id)
                await user.send(f"تم إغلاق تذكرتك في **{interaction.guild.name}**. فضلاً قيمنا:", view=view)
            except: pass
        await interaction.channel.delete()

# --- قائمة الأقسام عند فتح التيكت ---
class TicketDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="دعم فني", description="مشاكل تقنية أو برمجية", emoji="🛠️", value="Support"),
            discord.SelectOption(label="شكوى", description="تقديم بلاغ عن عضو أو مشكلة", emoji="⚠️", value="Complaint"),
            discord.SelectOption(label="استفسار", description="سؤال عن الرتب أو السيرفر", emoji="❓", value="General")
        ]
        super().__init__(placeholder="اختر قسم التذكرة...", options=options)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name=TICKET_CAT)
        staff = discord.utils.get(guild.roles, name=STAFF_ROLE)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        if staff: overwrites[staff] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=f"{self.values[0]}-{interaction.user.name}",
            category=category, overwrites=overwrites,
            topic=f"UserID:{interaction.user.id}"
        )

        embed = discord.Embed(title=f"قسم: {self.values[0]}", description="انتظر الموظف ليقوم بـ Claim للتذكرة.", color=0xf3c1cf)
        await channel.send(embed=embed, view=TicketControl())
        await interaction.response.send_message(f"تم فتح التذكرة: {channel.mention}", ephemeral=True)

class TicketOpenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())

# --- الأوامر ---
@bot.command()
@commands.has_permissions(administrator=True)
async def tsetup(ctx):
    log_cat = discord.utils.get(ctx.guild.categories, name=LOGS_CAT)
    if not discord.utils.get(ctx.guild.text_channels, name=FEEDBACK_CH):
        await ctx.guild.create_text_channel(FEEDBACK_CH, category=log_cat)
    if not discord.utils.get(ctx.guild.text_channels, name=TICKET_LOG_CH):
        await ctx.guild.create_text_channel(TICKET_LOG_CH, category=log_cat)

    embed = discord.Embed(title="📩 مركز الدعم - Uun", description="الرجاء اختيار القسم المناسب لمشكلتك من القائمة أدناه.", color=0xf3c1cf)
    await ctx.send(embed=embed, view=TicketOpenView())

@bot.event
async def on_ready():
    bot.add_view(TicketOpenView())
    bot.add_view(TicketControl())
    print(f"Uun System V2.0 Online!")

bot.run(os.getenv('DISCORD_TOKEN'))
