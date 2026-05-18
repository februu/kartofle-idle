import os
from datetime import datetime, timedelta
import discord
from discord.ext import commands
from discord import app_commands

from utils.embed import CustomEmbed
from utils.checks import guild_only
import db.controller as db

_UNIQUE_JOBS = os.getenv("UNIQUE_JOBS", "").lower() in {"1", "true", "yes", "on"}


### ---------------------------------------------- ###
###  Helper functions and logic for handling jobs  ###
### ---------------------------------------------- ###


async def autocomplete_jobs(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Autocomplete function for job selection. Filters jobs based on the current input."""
    jobs = db.get_jobs()
    return [
        app_commands.Choice(name=job.title, value=str(job.id)) for job in jobs if current.lower() in job.title.lower()
    ]


async def autocomplete_unassigned_jobs(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Autocomplete function for unique job selection. Filters jobs based on the current input."""
    jobs = db.get_unassigned_jobs()
    return [
        app_commands.Choice(name=job.title, value=str(job.id)) for job in jobs if current.lower() in job.title.lower()
    ]


async def start_job(user_id: int, job_id: str) -> tuple(str, str, str):
    """Starts a job for the user and returns the job title, amount and end time."""
    active_job_log = db.get_active_job_log_by_user(user_id)
    if active_job_log:
        return None, None, None

    job = db.get_job_by_id(int(job_id))
    end_time = datetime.now() + timedelta(seconds=job.duration_seconds)
    # Store without microseconds for clean time comparison
    end_time_iso = end_time.replace(microsecond=0).isoformat()
    db.create_job_log(user_id, int(job_id), end_time_iso)
    return job.title, job.amount, end_time_iso


async def get_active_job_status(user_id: int) -> str:
    """Checks if the user has an active job and returns its status."""
    is_active_in_job_log = db.get_active_job_log_by_user(user_id)
    if not is_active_in_job_log:
        job_text = "You're currently doing nothing. Maybe it's time to do smth?"
    else:
        job_log = is_active_in_job_log
        job = db.get_job_by_id(job_log.job_id)
        job_text = f"Working hard on {job.title} for {job.amount} until {job_log.end_time}."
    return job_text


async def has_active_job_assignment(job_id: int) -> bool:
    """Checks if a job is currently assigned to any user."""
    active_jobs = db.get_active_jobs()
    return any(j.id == job_id for j in active_jobs)


async def get_user_passive_income_status(user_id: int) -> str:
    """Checks if the user has active passive income and returns its status."""
    passive_incomes = db.get_passive_incomes_by_user(user_id)
    if not passive_incomes:
        return "You don't have any passive income sources. Maybe it's time to get some?"

    income_texts = []
    for income in passive_incomes:
        income_texts.append(
            f"{income.title}: {income.amount_per_second} per second (last settled: {income.last_settled})"
        )

    return "\n".join(income_texts)


### ---------------------------------------------- ###
###                 Jobs Cog                       ###
### ---------------------------------------------- ###


class JobsCog(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot

    @app_commands.command(name="job", description="Show status of your current job")
    @guild_only()
    async def job(self, interaction: discord.Interaction):
        job_text = await get_active_job_status(interaction.user.id)
        embed = CustomEmbed(title="Job status", description=job_text)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ubi", description="Show status of your Universal Basic Income")
    @guild_only()
    async def ubi(self, interaction: discord.Interaction):
        income_text = await get_user_passive_income_status(interaction.user.id)
        income_text += "\n-# Use **/ubis** to see available jobs."
        embed = CustomEmbed(title="Passive Income status", description=income_text)

        await interaction.response.send_message(embed=embed)

    if _UNIQUE_JOBS:

        @app_commands.command(name="work", description="Start doing some work")
        @app_commands.describe(job="Select your job")
        @app_commands.autocomplete(job=autocomplete_unassigned_jobs)
        @guild_only()
        async def work(self, interaction: discord.Interaction, job: str):
            if await has_active_job_assignment(int(job)):
                embed = CustomEmbed(
                    title="Failed to start the job",
                    description=f"This job is currently assigned to another user. \n-# Use **/jobs** to see available jobs.",
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            title, amount, end_time = await start_job(interaction.user.id, job)

            if (title, amount, end_time) == (None, None, None):
                embed = CustomEmbed(
                    title="Failed to start the job",
                    description=f"You already have an active job. \n-# Use **/job** to check its status.",
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            embed = CustomEmbed(
                title="Work started", description=f"Working hard on {title} for {amount} until {end_time}."
            )

            await interaction.response.send_message(embed=embed)

        @app_commands.command(name="jobs", description="Lists current available jobs")
        @guild_only()
        async def jobs(self, interaction: discord.Interaction):

            jobs = db.get_unassigned_jobs()
            if not jobs:
                jobs_text = "No jobs available."
            else:
                jobs_text = "\n".join(f"{j.id}: {j.title} — {j.amount} ({j.duration_seconds}s)" for j in jobs)
            embed = CustomEmbed(title="List of current available jobs", description=jobs_text)

            await interaction.response.send_message(embed=embed)

    else:

        @app_commands.command(name="work", description="Start doing some work")
        @app_commands.describe(job="Select your job")
        @app_commands.autocomplete(job=autocomplete_jobs)
        @guild_only()
        async def work(self, interaction: discord.Interaction, job: str):
            title, amount, end_time = await start_job(interaction.user.id, job)
            if (title, amount, end_time) == (None, None, None):
                embed = CustomEmbed(
                    title="Failed to start the job",
                    description=f"You already have an active job. \n-# Use **/job** to check its status.",
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            embed = CustomEmbed(
                title="Work started", description=f"Working hard on {title} for {amount} until {end_time}."
            )

            await interaction.response.send_message(embed=embed)

        @app_commands.command(name="jobs", description="Lists jobs")
        @guild_only()
        async def jobs(self, interaction: discord.Interaction):

            jobs = db.get_jobs()
            if not jobs:
                jobs_text = "No jobs available."
            else:
                jobs_text = "\n".join(f"{j.id}: {j.title} — {j.amount} ({j.duration_seconds}s)" for j in jobs)
            embed = CustomEmbed(title="List of jobs", description=jobs_text)

            await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(JobsCog(bot))
